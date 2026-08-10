# msr_image 장비 FTP 부하 감소 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이미지 서빙 경로가 계측 장비 FTP 서버에 여는 세션 수를 줄인다 — warm job 거부가 예산 없는 cold GET 폭주로 우회되는 경로를 막고(P1), 같은 파일에 대한 동시 요청을 장비 방문 1회로 합친다(A).

**Architecture:** 두 개의 독립적인 변경이다. P1 은 프론트엔드에서 warm job 의 429 거부를 `gaveup` 대신 jittered backoff 재시도로 바꿔 이미지 보류를 유지한다. A 는 백엔드 serve 경로에 캐시키별 프로세스 내 락을 넣고, **락 안에서 캐시를 다시 읽어** 앞선 요청이 채운 결과를 재사용한다. 새 의존성도, 계약 변경도 없다.

**Tech Stack:** Python 3.14 / Flask (백엔드, `pytest`), TypeScript / Nuxt 4 (프론트엔드, `node --test` 순수 함수만).

설계 근거: [`docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md`](../specs/2026-08-10-msr-image-tool-load-design.md)

## Global Constraints

- **계약 불변**: `GET /api/msr-image` 의 응답 바이트·헤더, 캐시 키, warm job 동작을 바꾸지 않는다.
- **집에서 Redis 없이 전체 스위트가 통과해야 한다.** 이번 범위에 Redis 를 쓰는 코드는 없다.
- **`download_all` / warm job 경로는 건드리지 않는다.** dedup 이 얻을 것이 없고, job 이 GET 을 기다리는 역전이 생긴다.
- **타임아웃을 새로 만들지 않는다.** 백엔드 fetch 는 `ftp_timeout`/`host_timeout` 이, 프론트 대기는 기존 `WARM_CEILING_MS = 15_000` 이 이미 묶고 있다.
- **429 판별은 상태 코드가 아니라 본문 `code === 'too_many_jobs'`** 로 한다. `/api/*` 전역 rate limit(20 req/5s)도 429 를 반환하며, 그것에 재시도로 답하면 상황을 악화시킨다.
- 스크립트/문서 규칙: 백엔드는 `.venv/bin/python -m ruff check .` 초록, Markdown 수정 시 `npm run lint:md`.
- 커밋은 **직접 편집한 파일 경로만 명시**해서 한다 (`git commit -- path/a path/b`). `git add -A` 금지.

---

### Task 1: warm 재시도 정책 (순수 함수)

프론트엔드의 결정 로직을 먼저 순수 함수로 만든다. `imageWarm.ts` 가 이미 `nextWarmState` 를 같은 방식으로 분리해 두었고, 그래야 `node --test` 로 검사할 수 있다.

**Files:**
- Modify: `front-dev-home/app/utils/imageWarm.ts` (파일 끝에 추가)
- Test: `front-dev-home/app/utils/imageWarm.test.ts` (신규)

**Interfaces:**
- Consumes: 기존 `WARM_CEILING_MS` (같은 파일).
- Produces: `WARM_RETRY_DELAYS_MS`, `warmErrorCode(err): string | undefined`, `jittered(baseMs, rand): number`, `warmRetryDelayMs(err, attempt, elapsedMs, rand): number | null`. Task 2 가 `warmRetryDelayMs` 만 호출한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-dev-home/app/utils/imageWarm.test.ts` 를 만든다:

```ts
// Pure-logic tests for the warm-job retry policy. Run:
//   node --test app/utils/imageWarm.test.ts
//
// The policy exists because a refused warm job used to become 'gaveup', which
// releases every held <img> at once — so the moment the tool is busiest, the
// screen fires N unbudgeted cold GETs at it. Waiting out the refusal is the
// whole point, and waiting out the WRONG 429 (the /api/* rate limit) would
// make a throttled client send more.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  WARM_CEILING_MS,
  WARM_RETRY_DELAYS_MS,
  jittered,
  warmErrorCode,
  warmRetryDelayMs,
} from './imageWarm.ts'

const refusal = { statusCode: 429, data: { code: 'too_many_jobs' } }
const rateLimited = { statusCode: 429, data: {} }

test('the job-cap refusal is recognised through the FetchError body', () => {
  assert.equal(warmErrorCode(refusal), 'too_many_jobs')
  assert.equal(warmErrorCode({ response: { status: 429 }, data: { code: 'too_many_jobs' } }), 'too_many_jobs')
})

test('a rate-limit 429 carries no job code, so it is NOT a refusal', () => {
  // Same status, opposite response: retrying a throttled client sends more.
  assert.equal(warmErrorCode(rateLimited), undefined)
  assert.equal(warmRetryDelayMs(rateLimited, 0, 0, 0.5), null)
})

test('a refusal retries on the configured backoff ladder', () => {
  // rand = 0.5 is the midpoint, so jitter cancels and the base shows through.
  assert.equal(warmRetryDelayMs(refusal, 0, 0, 0.5), WARM_RETRY_DELAYS_MS[0])
  assert.equal(warmRetryDelayMs(refusal, 1, 0, 0.5), WARM_RETRY_DELAYS_MS[1])
  assert.equal(warmRetryDelayMs(refusal, 2, 0, 0.5), WARM_RETRY_DELAYS_MS[2])
})

test('the ladder ends rather than repeating its last rung forever', () => {
  assert.equal(warmRetryDelayMs(refusal, WARM_RETRY_DELAYS_MS.length, 0, 0.5), null)
})

test('a non-429 failure gives up immediately', () => {
  // A dead tool or an expired job does not improve by waiting.
  assert.equal(warmRetryDelayMs(new Error('network down'), 0, 0, 0.5), null)
})

test('the ceiling wins over the ladder, and is checked BEFORE sleeping', () => {
  // Sleeping 4s only to then give up would hold the panel for nothing.
  assert.equal(warmRetryDelayMs(refusal, 0, WARM_CEILING_MS, 0.5), null)
  assert.equal(warmRetryDelayMs(refusal, 2, WARM_CEILING_MS - 1000, 0.5), null)
})

test('jitter stays inside +/-25% and moves with rand', () => {
  // Several users refused in the same instant must not retry in lockstep.
  assert.equal(jittered(1000, 0), 750)
  assert.equal(jittered(1000, 0.5), 1000)
  assert.equal(jittered(1000, 1), 1250)
})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd front-dev-home && node --test app/utils/imageWarm.test.ts`
Expected: FAIL — `WARM_RETRY_DELAYS_MS` / `warmErrorCode` / `jittered` / `warmRetryDelayMs` 를 export 하지 않음.

- [ ] **Step 3: 최소 구현을 쓴다**

`front-dev-home/app/utils/imageWarm.ts` 끝에 추가:

```ts
/** Waits before re-POSTing a refused warm job, in order. Sized so the whole
 * ladder fits inside WARM_CEILING_MS with polling time to spare. */
export const WARM_RETRY_DELAYS_MS = [1000, 2000, 4000] as const

/** The `code` a rejected $fetch carries, whatever shape Nuxt hands us.
 *
 * Status alone cannot decide this. `/api/*` has an application-wide 20 req/5s
 * limit that also answers 429, and warm polling at 600ms can reach it — but
 * only the job-cap refusal carries `too_many_jobs` (routes.py). Retrying the
 * other 429 would have a throttled client send more. */
export const warmErrorCode = (err: unknown): string | undefined =>
  (err as { data?: { code?: string } })?.data?.code

/** `baseMs` spread over +/-25%. `rand` is a caller-supplied [0,1) so the
 * policy stays a pure function; the caller passes Math.random(). Several
 * users refused in the same instant must not retry in lockstep. */
export const jittered = (baseMs: number, rand: number): number =>
  Math.round(baseMs * (0.75 + rand * 0.5))

/**
 * How long to wait before re-POSTing, or `null` to give up.
 *
 * `null` releases the held images to the cold-GET path, which is the old
 * behaviour — so every `null` here is a decision to accept that load.
 */
export const warmRetryDelayMs = (
  err: unknown,
  attempt: number,
  elapsedMs: number,
  rand: number
): number | null => {
  if (warmErrorCode(err) !== 'too_many_jobs') return null
  // Indexing past the ladder yields undefined, which IS the "stop" signal —
  // one check instead of a separate length guard, and no non-null assertion.
  const base = WARM_RETRY_DELAYS_MS[attempt]
  if (base === undefined) return null
  const delay = jittered(base, rand)
  // Checked before sleeping: waiting 4s only to then give up would hold the
  // panel for nothing.
  if (elapsedMs + delay >= WARM_CEILING_MS) return null
  return delay
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd front-dev-home && node --test app/utils/imageWarm.test.ts`
Expected: PASS (7 tests)

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: 오류 없음

- [ ] **Step 5: 커밋한다**

```bash
git add front-dev-home/app/utils/imageWarm.ts front-dev-home/app/utils/imageWarm.test.ts
git commit -m "feat(msr-image): warm job 거부를 기다릴지 판단하는 정책을 추가한다

429 를 상태 코드로만 보면 안 된다. /api/* 전역 rate limit(20 req/5s)도 429 를
내고 warm 폴링이 600ms 간격이라 실제로 닿을 수 있는데, 거기에 재시도로 답하면
이미 제한당한 클라이언트가 요청을 더 보낸다. job 상한 거부만 본문에
code=too_many_jobs 를 실으므로 그것이 유일하게 안전한 판별자다.

아직 배선하지 않았다. 다음 커밋에서 runWarm 이 쓴다."
```

---

### Task 2: `runWarm` 이 거부를 기다리게 한다

**Files:**
- Modify: `front-dev-home/app/composables/useMsrImageWarmer.ts:38-58` (`runWarm`)

**Interfaces:**
- Consumes: Task 1 의 `warmRetryDelayMs(err, attempt, elapsedMs, rand)`.
- Produces: 없음 (`runWarm` 은 모듈 내부 함수이며 시그니처가 그대로다).

- [ ] **Step 1: 현재 동작을 확인한다**

Run: `sed -n '33,60p' front-dev-home/app/composables/useMsrImageWarmer.ts`
Expected: `catch { state.status = 'gaveup' }` 한 블록이 보임. 이것이 429 와 죽은 장비를 똑같이 처리하는 지점이다.

- [ ] **Step 2: 재시도 루프로 바꾼다**

`import` 줄에 `warmRetryDelayMs` 를 추가한다:

```ts
import { WARM_POLL_MS, type WarmStatus, nextWarmState, warmRetryDelayMs } from '~/utils/imageWarm'
```

`runWarm` 본문을 통째로 교체한다:

```ts
/** POST the job, then poll it to completion, writing progress into `state`.
 *
 * A refused POST (the 2-job cap) is WAITED OUT rather than surfaced. Giving up
 * used to look harmless — the per-image cold GET still runs — but that path has
 * no session budget at all, so releasing the whole panel at the exact moment
 * the tool is saturated is what turns a cap into a stampede. Everything else
 * (dead tool, expired job) still gives up: waiting would not improve it. */
const runWarm = async (
  state: WarmState,
  api: ReturnType<typeof useMsrImageApi>,
  ctx: FocusImageCtx,
  names: string[]
) => {
  const startedAt = Date.now()
  for (let attempt = 0; ; attempt++) {
    try {
      const jobId = await api.startDownloadAll(ctx.eqp_ip, ctx.class_name, ctx.msr, names)
      for (;;) {
        await sleep(WARM_POLL_MS)
        const poll = await api.pollJob(jobId)
        state.done = poll.done
        state.total = poll.total
        state.status = nextWarmState(poll, Date.now() - startedAt)
        if (state.status !== 'warming') return
      }
    } catch (err) {
      // `attempt` counts POST refusals, and a refusal means no job was created
      // — so the retry re-POSTs rather than resuming a poll. There is no
      // job_id to resume.
      const delay = warmRetryDelayMs(err, attempt, Date.now() - startedAt, Math.random())
      if (delay === null) {
        state.status = 'gaveup'
        return
      }
      await sleep(delay)
    }
  }
}
```

- [ ] **Step 3: 상태가 유지되는지 확인한다**

`state.status` 는 `useMsrImageWarmer` 의 watch 에서 `'warming'` 으로 초기화되고 이 루프는 그것을 낮추지 않는다. 따라서 재시도 중 `SemImage.vue` 의 `holdForWarm` 이 계속 참이며 이미지가 보류된다 — 이 변경의 목적 그 자체다.

Run: `grep -n "status: 'warming'" front-dev-home/app/composables/useMsrImageWarmer.ts`
Expected: watch 안의 초기화 한 줄이 그대로 있음.

- [ ] **Step 4: 타입·린트·테스트를 돌린다**

Run: `cd front-dev-home && npm run typecheck && npm run lint && npm test`
Expected: 전부 통과

- [ ] **Step 5: 커밋한다**

```bash
git add front-dev-home/app/composables/useMsrImageWarmer.ts
git commit -m "fix(msr-image): warm job 거부에 이미지 폭주로 답하지 않는다

429 를 받으면 gaveup 으로 떨어져 보류가 풀리고, 화면의 모든 이미지가 예산 없는
cold GET 으로 동시에 나갔다. 장비가 가장 바쁠 때 — job 상한에 걸린 그 순간 —
부하를 묶으려고 만든 상한이 오히려 무제한 경로를 여는 스위치였다.

이제 거부는 jittered backoff 로 기다리고 보류를 유지한다. 죽은 장비나 만료된
job 은 지금처럼 gaveup 이다. 총 대기는 기존 WARM_CEILING_MS 예산을 그대로 쓰므로
사용자가 기다리는 최대 시간은 변하지 않는다."
```

---

### Task 3: single-flight 게이트 (백엔드, 순수 모듈)

**Files:**
- Create: `back_dev_home/msr_image/single_flight.py`
- Test: `back_dev_home/msr_image/tests/test_single_flight.py`

**Interfaces:**
- Consumes: 없음 (표준 라이브러리만).
- Produces: `fetch_gate(key: str)` — 컨텍스트 매니저. Task 4 가 이것만 쓴다. 디버깅/테스트용으로 `_locks` (dict) 를 모듈 수준에 노출한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`back_dev_home/msr_image/tests/test_single_flight.py`:

```python
"""The gate that keeps concurrent requests for one image to one tool visit.

The gate only provides mutual exclusion; the DEDUP comes from the caller
re-reading the cache inside it (see test_routes_serve). Both halves are needed
— exclusion alone would serialise the waiters and still send every one of them
to the tool, which is slower AND no lighter.
"""

import threading
import time

import pytest

from back_dev_home.msr_image.single_flight import _locks, fetch_gate


@pytest.fixture(autouse=True)
def _clean_registry():
    _locks.clear()
    yield
    _locks.clear()


def test_the_same_key_is_held_by_one_thread_at_a_time():
    order: list[str] = []

    def worker(name: str) -> None:
        with fetch_gate("img-a"):
            order.append(f"{name}-in")
            time.sleep(0.05)
            order.append(f"{name}-out")

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("t1", "t2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Whoever went first, no interleaving: an "in" is always followed by its
    # own "out".
    assert order[0].endswith("-in") and order[1].endswith("-out")
    assert order[2].endswith("-in") and order[3].endswith("-out")


def test_different_keys_do_not_block_each_other():
    """A single global lock would serialise a whole gallery's loading."""
    started = threading.Barrier(2, timeout=2.0)

    def worker(key: str) -> None:
        with fetch_gate(key):
            started.wait()  # times out and raises if the two are serialised

    threads = [threading.Thread(target=worker, args=(k,)) for k in ("img-a", "img-b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not started.broken


def test_an_exception_inside_the_gate_still_releases_it():
    """One tool error must not park a worker thread on that key forever."""
    with pytest.raises(RuntimeError):
        with fetch_gate("img-a"):
            raise RuntimeError("tool blew up")

    # Provable by the next acquisition succeeding without blocking.
    with fetch_gate("img-a"):
        pass


def test_the_registry_does_not_grow():
    """Keys are (msr, filename) pairs — unbounded, so entries must not leak."""
    for i in range(50):
        with fetch_gate(f"img-{i}"):
            pass
    assert _locks == {}


def test_a_waiter_keeps_the_entry_alive_while_it_waits():
    """Dropping the entry while someone still waits would hand the next
    arrival a DIFFERENT lock object, and the exclusion would be lost."""
    holder_in = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with fetch_gate("img-a"):
            holder_in.set()
            release.wait(timeout=2.0)

    t = threading.Thread(target=holder)
    t.start()
    holder_in.wait(timeout=2.0)
    assert "img-a" in _locks
    release.set()
    t.join()
    assert _locks == {}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_single_flight.py -q`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.msr_image.single_flight`

- [ ] **Step 3: 최소 구현을 쓴다**

`back_dev_home/msr_image/single_flight.py`:

```python
"""Keep concurrent requests for ONE image to one visit to the tool.

The measuring tool's FTP server caps concurrent sessions and engineers use
their own tools against the same equipment, so a session is a shared, scarce
resource. Two things make us open more of them than we need: the browser
re-requests a slow image at 2.5s and 5s (utils/imageRetry.ts), and two people
can open the same MSR at once. Both arrive as concurrent requests for the SAME
cache key, and each used to open its own session.

This module only provides the mutual exclusion. The dedup comes from the
caller re-reading the cache while holding the gate:

    with fetch_gate(cache_key(locator)):
        hit = cache.get(locator)          # did the request ahead of us fill it?
        if hit is not None:
            return hit                    # no tool visit
        ...

Without that re-read the waiters would simply take turns visiting the tool,
which is slower and no lighter.

Deliberately per-process and lock-free of any store: with one worker it is
exact, and with several the duplication drops from unbounded to the worker
count, which the shared MinIO cache already absorbs. A Redis lease would add
TTLs, polling and failure modes to buy that last factor.

There is no timeout. A waiter blocking IS the intent — the alternative is
giving up and going to the tool, which is the load this exists to prevent —
and the fetch it waits on is already bounded by ftp_timeout / host_timeout.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

# key -> (lock, how many callers hold or await it). The count is what lets the
# entry be removed safely: dropping it while someone still waits would hand the
# next arrival a different lock object and silently lose the exclusion.
_locks: dict[str, tuple[threading.Lock, int]] = {}
_registry_guard = threading.Lock()


@contextmanager
def fetch_gate(key: str) -> Iterator[None]:
    """Serialise callers sharing ``key``; release and clean up on the way out."""
    with _registry_guard:
        lock, waiting = _locks.get(key, (threading.Lock(), 0))
        _locks[key] = (lock, waiting + 1)

    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _registry_guard:
            held, waiting = _locks[key]
            if waiting <= 1:
                del _locks[key]
            else:
                _locks[key] = (held, waiting - 1)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_single_flight.py -q`
Expected: PASS (5 tests)

Run: `.venv/bin/python -m ruff check back_dev_home/msr_image/`
Expected: `All checks passed!`

- [ ] **Step 5: 커밋한다**

```bash
git add back_dev_home/msr_image/single_flight.py back_dev_home/msr_image/tests/test_single_flight.py
git commit -m "feat(msr_image): 이미지별 single-flight 게이트를 추가한다

계측 장비 FTP 는 엔지니어들과 나눠 쓰는 희소 자원인데, 같은 파일에 대한 동시
요청이 각각 세션을 열고 있었다. 브라우저가 느린 이미지를 2.5s/5s 에 다시 요청하고,
여러 사용자가 같은 MSR 을 동시에 열 수 있다.

게이트는 상호 배제만 제공한다. dedup 은 호출자가 게이트 안에서 캐시를 다시 읽는
데서 나온다 — 그것이 없으면 대기자들이 순서대로 장비에 다녀가므로 더 느리기만
하고 부하는 그대로다. 다음 커밋에서 배선한다.

타임아웃을 두지 않았다. 대기가 곧 의도이고(대안은 포기하고 장비에 가는 것),
기다리는 fetch 는 이미 ftp_timeout/host_timeout 으로 묶여 있다."
```

---

### Task 4: serve 경로에 배선하고 기록한다

**Files:**
- Modify: `back_dev_home/msr_image/routes.py:9-16` (import), `:170-174` (serve 블록)
- Test: `back_dev_home/msr_image/tests/test_routes_serve.py` (테스트 추가)
- Modify: `back_dev_home/msr_image/MIGRATION.md`

**Interfaces:**
- Consumes: Task 3 의 `fetch_gate`, 기존 `cache_key` (`back_dev_home.msr_image.cache`).
- Produces: 없음 (라우트 동작은 관측 가능한 범위에서 동일하다).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`back_dev_home/msr_image/tests/test_routes_serve.py` 끝에 추가:

```python
def test_concurrent_gets_for_one_image_make_one_tool_visit(tmp_path, monkeypatch):
    """The load this whole change exists to remove.

    Two requests for the same uncached image must cost the tool ONE session.
    The fetch is made slow on purpose: with a fast one the second request would
    find the cache already filled and pass even without the gate.
    """
    import threading
    import time

    from flask import Flask

    from back_dev_home.msr_image import data, routes
    from back_dev_home.msr_image.contracts import FetchedImage

    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    monkeypatch.setenv("IMAGE_CACHE_DIR", str(tmp_path))

    calls: list[str] = []
    calls_guard = threading.Lock()

    def slow_fetch(locator):
        with calls_guard:
            calls.append(locator.name)
        time.sleep(0.15)
        return FetchedImage(b"bytes", "image/jpeg", "mag=1")

    monkeypatch.setattr(data, "fetch_image", slow_fetch)

    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")

    url = "/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name=shot.jpeg"
    statuses: list[int] = []
    statuses_guard = threading.Lock()

    def hit():
        # A client per thread: Flask's test client is not shared-safe.
        r = app.test_client().get(url)
        with statuses_guard:
            statuses.append(r.status_code)

    threads = [threading.Thread(target=hit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert statuses == [200, 200]
    assert calls == ["shot.jpeg"], f"the tool was visited {len(calls)} times"


def test_concurrent_gets_for_different_images_both_fetch(tmp_path, monkeypatch):
    """The gate must be per image. A global one would serialise a gallery."""
    import threading

    from flask import Flask

    from back_dev_home.msr_image import data, routes
    from back_dev_home.msr_image.contracts import FetchedImage

    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    monkeypatch.setenv("IMAGE_CACHE_DIR", str(tmp_path))

    calls: list[str] = []
    calls_guard = threading.Lock()

    def counting_fetch(locator):
        with calls_guard:
            calls.append(locator.name)
        return FetchedImage(b"bytes", "image/jpeg", None)

    monkeypatch.setattr(data, "fetch_image", counting_fetch)

    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")

    def hit(name: str):
        app.test_client().get(
            f"/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name={name}"
        )

    threads = [threading.Thread(target=hit, args=(n,)) for n in ("a.jpeg", "b.jpeg")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(calls) == ["a.jpeg", "b.jpeg"]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_routes_serve.py -q -k concurrent`
Expected: 첫 테스트 FAIL — `the tool was visited 2 times`. 두 번째는 PASS (게이트가 없어도 통과하는, 회귀 방지용 테스트).

- [ ] **Step 3: serve 블록을 게이트로 감싼다**

`routes.py` 의 import 에 두 줄을 더한다:

```python
from back_dev_home.msr_image.cache import cache_key, make_cache
from back_dev_home.msr_image.single_flight import fetch_gate
```

`:170-174` 의 캐시 미스 분기를 교체한다 (앞뒤 줄은 그대로):

```python
        else:
            fetched = cache.get(locator)
            if fetched is None:
                # One visit to the tool per image, however many requests want
                # it. The re-read INSIDE the gate is what makes this a dedup
                # rather than a queue: the browser's own 2.5s/5s retries and a
                # second viewer all land here while the first fetch is still
                # running, and they must consume its result instead of opening
                # their own session. Keyed on the ORIGINAL (preview=False)
                # because a preview and a download of the same image are one
                # tool visit; the TIFF->WebP conversion below is our CPU, not
                # the tool's, and stays outside the gate.
                with fetch_gate(cache_key(locator)):
                    fetched = cache.get(locator)
                    if fetched is None:
                        fetched = data.fetch_image(locator)
                        cache.put(locator, fetched)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image -q`
Expected: PASS (기존 137 + 신규 7)

Run: `.venv/bin/python -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 5: MIGRATION.md 에 기록한다**

`back_dev_home/msr_image/MIGRATION.md` 의 "실측값" 절 바로 뒤에 추가:

```markdown
## 장비 부하 — 무엇이 세션을 여는가 (2026-08-10)

장비 FTP 는 엔지니어들과 나눠 쓰는 희소 자원이므로, 세션 수가 곧 우리가 지불하는
비용입니다. 두 경로가 장비에 접속합니다.

| 경로 | 예산 |
| --- | --- |
| warm job (`download_all`) | Redis 로 워커 간 `max_jobs` x `ftp_concurrency` |
| cold GET (`fetch_image`) | 이미지별 single-flight 게이트 (프로세스 내) |

cold GET 은 예산이 없었고 같은 파일에 대한 동시 요청마다 세션을 열었습니다. 이제
`single_flight.fetch_gate` 가 캐시키별로 묶고, 게이트 안에서 캐시를 다시 읽어
앞선 요청의 결과를 재사용합니다.

커넥션 풀링은 **하지 않습니다.** 유휴 세션이 장비 슬롯을 점유해 이 목표와 정면으로
충돌합니다. 근거는 `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md`.
```

Run: `npm run lint:md`
Expected: `Summary: 0 error(s)`

- [ ] **Step 6: 커밋한다**

```bash
git add back_dev_home/msr_image/routes.py back_dev_home/msr_image/tests/test_routes_serve.py back_dev_home/msr_image/MIGRATION.md
git commit -m "fix(msr_image): 같은 이미지에 대한 동시 요청을 장비 방문 1회로 합친다

serve 경로의 캐시 미스 분기를 이미지별 게이트로 감싸고, 게이트 안에서 캐시를 다시
읽는다. 브라우저의 2.5s/5s 재시도와 두 번째 사용자가 첫 fetch 가 도는 동안 여기
도착하는데, 지금까지는 각자 세션을 열었다.

키는 원본(preview=False)이다. preview 요청과 원본 다운로드가 같은 1장을 받으므로
장비 방문 기준으로 합쳐야 하고, TIFF->WebP 변환은 우리 CPU 비용이라 게이트 밖에
둔다.

느린 fetch 로 실제 경합을 만들어 검증했다 — 빠른 fetch 로는 두 번째 요청이 이미
채워진 캐시를 만나 게이트 없이도 통과한다."
```

---

### Task 5: 전체 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 백엔드 전체 스위트**

Run: `.venv/bin/python -m pytest -q`
Expected: 기존 대비 신규 7건 증가, 실패 0

- [ ] **Step 2: 프론트엔드 전체**

Run: `cd front-dev-home && npm test && npm run typecheck && npm run lint`
Expected: 전부 통과

- [ ] **Step 3: 정적 게이트**

Run: `.venv/bin/python -m ruff check . && npm run lint:md`
Expected: 둘 다 초록

- [ ] **Step 4: 집에서 실제로 띄워본다**

`.venv/bin/python index.py` 와 `cd front-dev-home && npm run dev` 를 띄우고
Skewvoir 의 SEM 이미지 패널을 연다. 집은 mock provider 라 장비 부하 자체는
재현되지 않지만, **이미지가 여전히 뜨는지**(계약 불변)와 콘솔 오류가 없는지를 본다.

Expected: 이미지 렌더, 콘솔 오류 없음

- [ ] **Step 5: 푸시**

```bash
git push
```

## 사무실에서 확인할 것

집에서는 mock provider 라 장비 세션 수가 재현되지 않는다. 사무실 배포 후:

1. warm job 두 개를 띄워 상한을 채운 상태에서 세 번째 MSR 을 연다 — 이미지가
   `준비 중` 으로 보류되어야 하고, 곧바로 이미지 요청이 나가면 안 된다.
2. 서버 로그에서 한 이미지에 대한 `fetch_image` 호출이 동시 요청 수만큼 찍히지
   않는지 본다.
