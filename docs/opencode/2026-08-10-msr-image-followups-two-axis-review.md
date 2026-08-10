# msr_image 후속 이슈 4건 구현 — opencode oc-review 기록

- 실행일: 2026-08-10
- 스킬: oc-review
- 모델: `opencode-go/kimi-k3` (tier=heavy)
- 대상: `git diff c3b38a11...HEAD` — msr_image 후속 이슈 01–04 구현 커밋 6개 (16 files, +729/-206)
- 소요: Standards 247초 (`ses_0147f451bffegwgEspID38zdcq`) · Spec 473초 (`ses_0147f4330ffew1X6gwx6aRh6VB`)
- 결과: 두 축 모두 성공

동시성 프리미티브(`single_flight.py`)와 재시도·타임아웃 정책을 함께 바꾸는
변경이므로 `models.md` 의 escalation 규칙에 따라 `heavy` 로 실행했습니다.

## 모델이 지적한 것 — Standards 축 (원문 인용)

> Now let me read the documented standards.
> I've inspected the full diff, the commits, and the three standards documents. Here is the review.
>
> ## (a) Documented-standard breaches (HARD)
>
> **None found.** Checked against:
>
> - **CLAUDE.md** — no office-DB facts added, so the "two places" mock/doc rule is not triggered; `.scratch/` edits are explicitly unlinted scratch (line 216), so no `lint:md` obligation there; the edited `docs/superpowers/specs/...md` uses compact MD060 tables and formal `~입니다/합니다` endings; no `data.py` or `office.py` touched.
> - **MIGRATION.md** (`msr_image`) — the `single_flight` semantics change is documented there in the same change (§"장비 부하"), satisfying the keep-docs-current expectation; the "edit only `providers/office.py`" rule governs office-adapter work, not this home-side feature change.
> - **DESIGN.md** — no UI/styling in the diff; out of scope.
>
> The removal of `statusOf` from `useMsrFileApi.ts` in favour of the shared `httpStatus` actively *fixes* a pre-existing duplication.
>
> ## (b) Baseline smells (JUDGEMENT)
>
> 1. **Duplicated Code (weak)** — `front-dev-home/app/utils/imageWarm.ts`. Two one-liners differ only in the `(status, code)` pair:
>
>    ```ts
>    export const isWarmRefusal = (err) => httpStatus(err) === 429 && warmErrorCode(err) === 'too_many_jobs'
>    const isJobGone = (err) => httpStatus(err) === 404 && warmErrorCode(err) === 'unknown_job'
>    ```
>
>    A shared `hasStatusAndCode(err, status, code)` would carry both. Two occurrences of a one-liner — extraction is borderline; judge's call.
>
> 2. **Duplicated Code (weak)** — `back_dev_home/msr_image/tests/test_single_flight.py`. The `leader_in`/`release` blocking-fetch scaffolding repeats across `test_one_fetch_serves_every_caller_that_asked_at_once`, `test_the_waiters_are_all_released_at_once`, and `test_a_leader_that_returns_none_is_still_an_answer`. A small fixture/helper would shrink all three; per-test explicitness may be the house style, so weak.
>
> 3. **Data Clumps (weak, pre-existing)** — `useMsrImageApi.ts`: `startDownloadAll(eqp_ip, class_name, msr, names, timeoutMs)` adds a fifth positional param to the existing `(eqp_ip, class_name, msr)` clump that `FocusImageCtx` already types. Not introduced by this diff, only widened.
>
> 4. **Doc/code terminology drift** — `back_dev_home/msr_image/MIGRATION.md` line 52's table still says "이미지별 **single-flight 게이트**" while the new `single_flight.py` docstring explicitly states "this is not mutual exclusion" — the gate metaphor is what the change retired. The MIGRATION body prose was updated; the table entry was not.
>
> ## Notes (not flagged)
>
> - No **mock/office formula drift**, **unmarked office assumption**, **doc/mock split**, or **value-domain narrowing** — no provider or mock changes; new tests cover the `None`-outcome domain edge explicitly.
> - The `leading = attempt is None` / `if attempt is None:` double condition in `single_flight.py` is trivial; not worth a finding.
> - Retry-budget reasoning (`retry: 0`, `remainingBudgetMs`) matches the documented ofetch behaviour and the §4.1/§9 spec amendments.
>
> **Verdict: no HARD breaches; four weak JUDGEMENT items, all optional.**

## 모델이 지적한 것 — Spec 축 (원문 인용)

> Now let me check the issue-file diffs (to see if 검증 sections were edited = goalpost moving), and the rest of the relevant code.
> Now let me verify the remaining claims: leftover references, other callers, the concurrency tests in `test_routes_serve.py`, and the `.ts`-extension import convention.
> Two more checks: the current `single_flight.py` in full, and the test fixtures in `imageWarm.test.ts`.
> One last verification — the actual refusal/unknown_job branches in `routes.py`, since issues 02/04 hinge on them.
> Verification complete. Premises check out (`too_many_jobs` only at 429 in routes.py:296/316; `unknown_job` 404 is the only poll failure, :330), the settled judgments are respected (`done.wait()` bare, unpublish-before-wake kept, no warm-path gating, no re-POST, no second ceiling constant), and all promised test cases for 02 (4/4, both Nuxt error shapes) and 04 (5/5) exist. Findings:
>
> **(a) Missing / partly done**
>
> 1. **Issue 01's promised red test does not exist.** 검증 says: "**새 테스트**: 느린 `cache.get` 을 주입하고 대기자 3명을 붙였을 때, 전체 소요가 캐시 읽기 1회 수준이어야 하고 3회가 누적되면 안 됩니다. **지금 코드에 대해 실패해야 합니다**". Delivered instead is `test_the_waiters_are_all_released_at_once` — a Barrier property test with no slow `cache.get`, no read counting, never run red. The Answer's "쓸 수 없습니다" is only true post-refactor; a failing test against the old `with`-block signature was writable before the rewrite. Disclosed openly, but the criterion as written is unmet — the one visible goalpost move.
> 2. **Issue 03's response-independence is untested.** 검증: "그 판정이 응답 도착 여부와 무관한지". The mechanism delivering it is the `$fetch` timeout wiring in `budgeted()`; only `remainingBudgetMs` arithmetic has tests. The issue excuses timer-tangled parts, so per-spec, but the actual ceiling enforcement has zero coverage.
>
> **(b) Scope creep**
>
> 3. `useMsrFileApi` refactor (`statusOf` → shared `httpError.ts`) — no issue asked to touch it; 02 only cited it as precedent ("status 추출은 저장소에 이미 선례가 있습니다 — useMsrFileApi.ts:162"). Small, disclosed, behavior-preserving.
> 4. `retry: 0` on `$fetch` — in no issue's 제안; disclosed in 03's Answer with a real justification (ofetch's default GET retry would double-spend the budget).
>
> **(c) Implemented but looks wrong**
>
> 5. **Poll retries sleep twice.** Issue 04: "1+2+4 = 7s 의 관용은 15s 예산 안에 들어갑니다". In `runWarm`, after `pollRetryDelayMs`'s delay, `continue` lands on `await sleep(WARM_POLL_MS)` before the next poll — each retry costs delay+600ms (~8.8s real), and the ladder guard `elapsedMs + delay >= WARM_CEILING_MS` ignores the trailing 600ms, so the panel can hold up to one poll interval past the ceiling. Conservative direction; minor.
>
> Spec.md's amendments (슬롯-점유 rationale, the "이 근거는 이슈 01 이 고쳐진 뒤에야 참" caveat, issue 04 itself) read as genuine findings, not goalpost moves; the design-doc §4.1 amendment is explicitly sanctioned ("04 는 설계 문서에 대한 **수정** 입니다").

## 판단

| 축 | 지적 | 처리 | 사유 |
| --- | --- | --- | --- |
| Spec | 폴링 재시도가 두 번 잔다 (backoff 뒤 `continue` 가 `sleep(WARM_POLL_MS)` 로 되돌아감) | 채택 | 사실입니다. 재시도 1회의 실제 비용이 delay+600ms 이고, 사다리의 상한 검사는 그 600ms 를 세지 않아 패널이 최대 한 폴링 간격만큼 상한을 넘깁니다. 대기 변수 하나로 고칩니다 |
| Standards | `MIGRATION.md` 표가 아직 "single-flight 게이트" 라고 부름 | 채택 | 본문은 고쳤는데 표를 놓쳤습니다. 이 변경이 없앤 것이 바로 게이트(상호 배제) 은유입니다 |
| Spec | 이슈 01 이 요구한 "지금 코드에 대해 실패하는" 테스트가 없음 | 인정, 조치 없음 | 모델 지적이 정확합니다. 리팩터 **전에** 옛 `with` 시그니처로 red 테스트를 쓸 수 있었고, 그 순서를 밟지 않았습니다. 지금은 옛 구현이 없어 사후에 만들 수 없습니다. 대체한 Barrier 성질 테스트와 그 한계는 테스트 docstring 과 이슈 Answer 에 적어 뒀습니다 |
| Spec | 이슈 03 의 "응답 도착 여부와 무관한지" 가 미검증 | 보류 | 실효 상한을 만드는 것은 `$fetch` timeout 배선인데, 이 저장소에는 컴포넌트 마운팅 하네스도 E2E 스위트도 없어 순수 함수 밖은 검사할 수단이 없습니다. 이슈 자체가 그 부분을 면제했습니다 |
| Standards | `isWarmRefusal`/`isJobGone` 을 `hasStatusAndCode(err, status, code)` 로 합치기 | 반려 | 두 판별자는 같은 모양이지만 같은 이유가 아닙니다 — 하나는 "기다리면 풀리는 거부", 다른 하나는 "기다려도 없는 job" 이고, 각자의 docstring 이 그 근거를 답니다. 공통 헬퍼로 접으면 호출부에 남는 것은 숫자와 문자열뿐이라 그 근거가 갈 곳이 없어집니다 |
| Standards | 테스트의 `leader_in`/`release` 스캐폴딩 중복 | 반려 | 이 저장소의 테스트는 픽스처보다 각 테스트가 자기 시나리오를 통째로 보여 주는 쪽입니다. 동시성 테스트에서는 특히 어느 스레드가 언제 막히는지가 테스트 본문에 보여야 합니다 |
| Standards | `startDownloadAll` 의 위치 인자 clump | 반려 | 지적대로 기존 것이고, `imageUrl`·`fetchImageWithCond` 가 같은 세 인자를 같은 방식으로 받습니다. 이 컴포저블만 `FocusImageCtx` 를 받으면 그 일관성이 깨집니다 |
| Spec | `useMsrFileApi` 의 `statusOf` 정리, `$fetch` 의 `retry: 0` (scope creep) | 반려 | 둘 다 범위를 넘긴 것은 맞으나, 전자는 Standards 축이 같은 회차에 중복으로 지적한 것이고 후자는 없으면 예산이 요청 하나만큼 어긋납니다. 각각 커밋 메시지와 이슈 Answer 에 사유를 남겼습니다 |

## 후속

- 채택 2건(폴링 이중 대기, MIGRATION 표 문구)을 이어지는 커밋에서 반영합니다.
- 이슈 01 의 red 테스트 누락은 되돌릴 수 없으므로 기록으로 남깁니다. 다음에
  프리미티브 모양을 바꾸는 작업에서는 시그니처를 바꾸기 **전에** 현재 동작에
  대한 실패 테스트를 먼저 남겨야 합니다.
