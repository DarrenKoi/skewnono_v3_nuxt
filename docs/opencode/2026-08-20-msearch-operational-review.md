# msearch 를 적용해도 운영에 무리가 없는가 — 2축 검토

- 일자: 2026-08-20
- 스킬: `oc-review` (diff 가 없어 축을 "운영 리스크" / "표준·기존 결정 대조" 로 재정의)
- 모델: `glm-5.3` (variant `high`, tier `heavy`)
- 세션: `ses_fe43b32e7ffeoxcvFCJcXJYdeb` (ops), `ses_fe43b32eaffeKG2Zed2hCYJ807` (standards)
- 소요: 74초 / 95초, 두 축 병렬
- 질문: (1) msearch 로 적용했을 때 웹 애플리케이션 운영에 무리가 없는가,
  (2) `ops_store` 에 적용하면 기존 코드를 바꾸지 않아도 되는가

## 이 검토의 전제

리뷰할 diff 가 없습니다. 작업 트리는 깨끗하고 `msearch` 라는 문자열은 저장소
전체에서 어제의 논쟁 기록 한 건에만 등장합니다. 따라서 이 문서는 **아직
작성되지 않은 변경에 대한 사전 검토**이며, 두 축 모두 현재 코드를 읽고
"도입하면 무엇이 달라지는가" 를 답하도록 지시했습니다.

`heavy` 티어를 고른 이유는 크기가 아니라 표면입니다. `_office_search.py` 는
모든 e-beam office 어댑터가 통과하는 단일 접근 계층이고, 사무실 DB 가 집에서
닿지 않으므로 **어느 쪽이 맞든 집 테스트는 통과합니다**.

## Claude 가 위임 전에 직접 확인한 사실

| 사실 | 근거 |
| --- | --- |
| `ops_store.OSSearch` 에 msearch 메서드가 없습니다 | 전 메서드가 `search_raw()` → `client.search()` 한 갈래로 수렴 |
| `aggregate()` 의 검증 사다리는 응답이 하나라는 전제 위에 있습니다 | `timed_out` · `_shards.failed` · `aggregations` 를 최상위에서 한 번 검사 |
| 실패가 SPA 에 닿는 경로는 예외 타입으로 결정됩니다 | `NotFoundError`→`LookupError`→502, `RuntimeError`→503 |
| 운영 프로세스 모델은 4 프로세스 × 4 스레드 = 16 슬롯입니다 | `wsgi.ini`, `harakiri = 120` |
| 클라이언트는 30초 타임아웃에 3회 재시도합니다 | `ops_store/base.py`, `retry_on_timeout = True` |

## 운영 리스크 축 — 모델 답변 (verbatim)

## 1. Operational safety

**BLOCKING — error semantics inversion.** msearch answers HTTP 200 with per-sub-request `{"error":…, "status":404}` bodies, so the driver never raises `NotFoundError`. The entire current failure path dies silently:

- `back_dev_home/ebeam/_office_search.py:153` — `except NotFoundError as exc: raise _missing_index_error(index, exc)` stops firing. A missing alias no longer becomes the SPA's `502 upstream_data_error` ("OpenSearch index/alias 'x' not found").
- Instead the body falls into the ladder and dies at `_office_search.py:161` — `timed_out = result.get("timed_out"); if timed_out is not False: raise RuntimeError(...)` — which `back_dev_home/__init__.py:140` maps to **503 `backend_unavailable`**. User sees "backend unavailable" for a data problem, with a message about `timed_out` metadata that names nothing actionable.

**BLOCKING if skipped, MANAGEABLE if done — the validation ladder.** `timed_out is not False`, `_shards.failed != 0` (`refusing partial aggregation results`), and the `aggregations` Mapping check are written against one response. Under msearch they must be re-applied **per sub-response**; msearch has no envelope `_shards`. Skip that and `_shards.failed>0` partial results reach `office_example.py`'s bucket math as valid numbers — user sees plausible-but-wrong `para_*` totals, no error anywhere.

**MANAGEABLE — timeouts/occupancy.** `ops_store/base.py:30-32` (`timeout: int = 30`, `max_retries: int = 3`, `retry_on_timeout: bool = True`) keeps one batch under `wsgi.ini:60` `harakiri = 120`. But `processes = 4` / `threads = 4` = 16 slots, and one batch = one slow query blocking all its siblings; a 30s+retries batch pins a slot where today's queries return independently.

**MANAGEABLE — shared cluster.** Sub-query concurrency is the cluster's `max_concurrent_searches`, not ours, on a cluster we share and cannot measure from home. Burst impact on other teams is untestable before shipping.

**NOT-A-RISK — rate limit.** `__init__.py:95` `application_limits=["50 per 5 seconds"]` counts our `/api` endpoints, not OS round trips.

## 2. The ops_store question

**Yes, purely additive is structurally possible — and buys nothing by itself.** Every existing method funnels through one choke point, `ops_store/search.py:112`:

```python
def search_raw(self, body: dict[str, Any], *, index: str | None = None) -> dict[str, Any]:
    name = self._resolve_index(index)
    return self.client.search(index=name, body=body)
```

A new `def msearch(self, bodies, *, index=None)` reusing `_resolve_index` and calling `self.client.msearch(...)` touches no existing call site; `NotFoundError` handling in `latest()` and response-shape assumptions in `to_dataframe` are untouched because nothing existing routes through the new method. Zero behaviour change for current callers: **holds**.

But the real edit surface is elsewhere, and cannot be additive:

- `back_dev_home/ebeam/_office_search.py:148` `aggregate(index, aggs, query_body)` and `:231` `fetch_hits(index, query_body, size, sort, source)` are the only entry points adapters use. A batching variant means a new `aggregate_many()` **plus** rewriting every consumer loop — `office_example.py:1005` `for start in range(0, len(unique), _IDP_CHUNK):`, `_r3_steps`, `_mfab_steps` — to collect queries and split sub-responses. That is the per-sub-response validation problem from §1, now duplicated per adapter unless centralized in `_office_search.py`.
- `ops_store/` is a vendored byte-copy: the new method must land in upstream `flask_modules` simultaneously (Vendored-module edit smell), and the office runtime may load the upstream copy.
- `office.py` is gitignored — adapter edits ship only via re-copy.

## 3. Minimum viable adoption

**Honest answer: no change is justified.** I do **not** disagree with the recorded debate — its load-bearing fact checks out: `_IDP_CHUNK = 500` against "device 당 recipe 100~200개" means the "heaviest consumer" is normally **one** request already; the supposed payoff is one round trip saved on a path that mostly doesn't loop. Capping that with untestable error-semantics and shared-cluster risk is indefensible.

If forced anyway, smallest defensible slice: (1) `msearch` added to upstream `flask_modules` **and** the vendored copy together; (2) one new `_office_search.aggregate_many()` that applies the existing ladder verbatim per sub-response and maps sub-response `status:404` to `LookupError` (preserving the 502 contract); (3) sub-batch cap ≤5; (4) env-flagged with cross-run A/B logging (per the doc's `ttl_cache` 900s warm-order point); (5) a mock contract test proving batched ≡ sequential. **Before it ships:** the already-agreed per-request timing instrumentation must show a real multi-round-trip hotspot on the actual cluster — which today's code says does not exist.

## 표준·기존 결정 축 — 모델 답변 (verbatim)

## (a) Standards breached

**1. Vendored-copy rule — the hard one.** CLAUDE.md:211–215: vendored copies "`ftp_handler/`, `minio_handler/`, `ops_store/`, `ops_index_mgmt/` … must stay **byte-identical to their upstream**". The project smell baseline names it too: "Vendored-module edit — … Editing one copy alone is a defect." `ops_store/search.py` is such a copy (its own docs reference the upstream `flask_modules` checkout). Adding `msearch` there breaches the rule outright; the next upstream sync silently drops it. The compliant home is `_office_search.py`, which is TRACKED by design — its docstring says it "holds no 사내 schema details, only access mechanics" — and bm_pm's `_diagnose` already calls the raw `os_client.search(...)` directly (bm_pm/office_example.py:247–256), so raw-client precedent exists.

**2. Stale-copy propagation.** CLAUDE.md:49–50: "Because `office.py` is a copy, a `git pull` that moves the template leaves the running adapter serving 200s from old code." The STALE-office.py detector compares *template* shas; a change to tracked shared plumbing fires no warning at all. This is survivable **only if** the plumbing change is strictly additive — old copies then simply don't call the new entry point. Any behavioural change to `aggregate()`/`fetch_hits()` would reach running office copies unannounced. provider-selection.md §5 additionally notes `EDITED` copies are never force-overwritten, so actually *using* msearch means hand-updating every office copy on a scarce office visit.

## (b) Additivity in `ops_store/search.py`

Technically additive. Every existing method funnels through one choke point — `search_raw`: "`return self.client.search(index=name, body=body)`" (search.py:119); `count` and `_search_all_hits` are the only other direct `self.client` callers. The class holds no state beyond `self.client`/`default_index`; a sibling `def msearch(...)` calling `self.client.msearch(...)` disturbs nothing. **But it is still prohibited by (a)** — additive to the class, defect to the vendoring convention. Verdict: additive in mechanics, not permissible in location; the addition belongs in `_office_search.py` over `client()`.

## (c) Contradiction with 2026-08-20

Direct contradiction. The recorded agreement: "**결론: 계측만 출하하고 그 외에는 아무것도 하지 않습니다. 살아남는 병렬화 대상이 없습니다.**" (ship instrumentation only; no surviving parallelisation target), with msearch's "진짜 위험" being per-response error semantics inside HTTP 200. Moreover, the gate that decision erected is unmet: commit `e65de1b8` landed *only the doc* — `_office_search.py` today carries no per-request timing, so the measurement that was to justify any second change was never shipped.

On the merits, I would not overturn it: the conclusion came from candidate-by-candidate elimination (bm_pm withdrawn behind a live 9-hour anchor bug; `_IDP_CHUNK=500` a cap defense, not a bottleneck), and the error-semantics cost is real — `aggregate()` currently validates `timed_out`/`_shards.failed` per response (`_office_search.py:160–188`); msearch requires re-applying that per sub-response. The decision stands unless instrumentation later shows a real fan-out cost.

## (d) Smells

- **Vendored-module edit** (project) — `ops_store/search.py` modification, per (a).
- **Speculative Generality** — batching added with no measured bottleneck; the prior review found no surviving target.
- **Duplicated Code** — any `_office_search.py` msearch entry point re-implements `aggregate()`'s NotFoundError→LookupError mapping and metadata validation unless extracted.
- **Shotgun Surgery** — one logical change spans `ops_store` or `_office_search.py` plus every `office_example.py` template and a per-feature office re-`cp`.

## Claude 의 판단

### 인용 검증

인용된 줄을 전부 열어 확인했습니다. 한 건은 문서가 모델이 말한 것과 다른
말을 합니다.

| 인용 | 검증 결과 |
| --- | --- |
| `_office_search.py:153` `except NotFoundError` | 정확합니다 |
| `_office_search.py:161` `timed_out` | 실제로는 160행이며, 내용은 정확합니다 |
| `_office_search.py:148` `aggregate` / `:231` `fetch_hits` | 정확합니다 |
| `__init__.py:140` `RuntimeError`→503 | 데코레이터 140행·함수 141행, 매핑은 정확합니다 |
| `__init__.py:95` `application_limits=["50 per 5 seconds"]` | 정확합니다 |
| `ops_store/base.py:30-32` timeout 30 · retries 3 · retry_on_timeout | 정확합니다 |
| `wsgi.ini:60` `harakiri = 120`, 4×4 | 정확합니다 |
| `ops_store/search.py:112` · `:119` `search_raw` | 정확합니다 |
| `e65de1b8` 이 문서만 담았다 | 정확합니다. `_office_search.py` 에 계측이 없음을 재확인했습니다 |
| bm_pm `:247-256` 의 raw client 선례 | **약화됩니다** (아래) |
| CLAUDE.md `:211-215` vendored 규칙 | **부분적으로 틀렸습니다** (아래) |

**bm_pm 의 raw client 선례는 요청 경로의 선례가 아닙니다.** 해당 코드는
`_diagnose()` 안에 있고 `# pragma: no cover` 가 붙은 `__main__` 스모크
테스트입니다. "raw client 를 직접 부르는 전례가 있다" 는 사실이지만, 그것이
정당화하는 것은 진단 스크립트이지 요청 중에 도는 코드가 아닙니다. 결론
(`_office_search.py` 가 맞는 자리)은 유지되나 근거는 이것이 아니라 그 모듈이
TRACKED 라는 사실입니다.

**vendored 규칙 인용은 다른 절에서 왔습니다.** "must stay byte-identical to
their upstream" 이라는 문구는 CLAUDE.md 에 실제로 있으나, 그 위치는
**Markdown Notes 의 markdownlint glob 절**이며 "이들 트리는 lint 대상에서
빼둔다" 의 이유로 적힌 문장입니다. 저장소의 실제 규약은 "고치지 말라" 가
아니라 **"두 사본을 함께 고쳐라"** 입니다. 따라서 이 항목은 BLOCKING 표준
위반이 아니라 **두 저장소 동시 변경이라는 조율 비용**으로 내려갑니다. 다만
결론은 바뀌지 않습니다 — 사무실에서만 가능한 조율을, 이득이 상한에 걸린
변경을 위해 쓰는 것은 여전히 정당화되지 않습니다.

### 동의하는 부분

- **에러 시맨틱 역전이 최대 위험**이라는 진단에 전면 동의합니다. 어제 논쟁이
  같은 지점을 짚었고, 오늘 코드를 다시 읽어도 그대로입니다. 하위 응답이
  `{"error": …, "status": 404}` 로 오면 `result.get("timed_out")` 은 `None` 이
  되고, 그 값은 `is not False` 이므로 사다리의 첫 관문에서 `RuntimeError` 로
  죽습니다. 즉 **"인덱스가 없다"(502)가 "백엔드를 못 쓴다"(503)로 둔갑**하고,
  메시지는 사용자가 할 수 있는 일을 하나도 말하지 않습니다.
- **`ops_store` 추가 자체는 기계적으로 additive** 라는 판정에 동의합니다. 클래스
  상태가 `client` 와 `default_index` 뿐이고 모든 기존 메서드가 `search_raw` 로만
  수렴하는 것을 확인했습니다.
- **지금은 하지 않는다**는 결론에 동의합니다.

### 두 축이 놓친 것

1. **`_resolve_index` 가 `OSSearch` 를 인덱스 하나에 묶습니다.**
   `_office_search.search(index)` 는 호출마다 `OSSearch(client=client(),
   index=index)` 를 새로 만듭니다. 그런데 msearch 의 존재 이유는 **서로 다른
   index·query 쌍을 한 번에 보내는 것**입니다. 인덱스에 묶인 객체에 매달린
   msearch 메서드는 (a) `_resolve_index` 를 무시하고 하위 요청마다 인덱스
   헤더를 받거나, (b) 같은 인덱스 질의만 배치하거나 둘 중 하나인데, (a)는 그
   메서드만 클래스의 규약을 벗어나고 (b)는 이득의 대부분을 버립니다. "additive
   하다"는 참이지만 **그 자리에 놓기에 어울리는 메서드가 아니라는 것**이
   두 축이 놓친 설계 신호입니다.

2. **실패의 폭발 반경이 뒤집힙니다.** 오늘 `_shards.failed != 0` 은
   "부분 집계 결과를 거부한다" 는 정책이고, 죽는 것은 **질의 하나**입니다.
   배치에서는 하위 응답 하나의 샤드 실패가 (a) 순진하게 구현하면 배치 전체를
   죽여 **오늘이면 일부라도 그려지던 화면을 통째로 실패**시키거나, (b) 하위
   응답별로 넘어가면 그 정책이 조용히 무력화됩니다. 두 축 모두 "하위 응답마다
   검증을 재적용해야 한다" 까지는 말했으나, 재적용한 뒤에 **무엇을 실패로
   칠 것인가**라는 정책 결정이 새로 생긴다는 점은 말하지 않았습니다.

3. **재시도 증폭이 harakiri 경계와 만납니다.** `timeout=30` 에 `max_retries=3`,
   `retry_on_timeout=True` 이므로 최악의 경우 4회 × 30초 = 120초이고, 이는
   `harakiri = 120` 과 정확히 같습니다. 산술적 천장은 오늘도 같지만 배치는 두
   가지를 바꿉니다 — 재시도 1회가 **N 개 질의를 공유 클러스터에 다시
   실행**시키고, 배치 지연이 가장 느린 하위 질의에 지배되므로 그 천장에 훨씬
   자주 닿습니다. `wsgi.ini` 가 직접 적어둔 대로 harakiri SIGKILL 은 워커
   전체를 죽이며 **같은 워커의 다른 3개 스레드가 처리 중이던 요청까지 함께
   죽습니다.** ops 축은 "슬롯을 오래 점유한다" 까지만 말했습니다.

4. **배치 가능한 집합이 사실상 비어 있습니다.** 이것이 나머지 논의를 무의미하게
   만드는 지점입니다. 어댑터의 질의는 대체로 **데이터 의존**입니다 —
   device 를 알아야 recipe 를 묻고, recipe 를 알아야 parameter 를 묻습니다.
   msearch 는 **같은 시점에 이미 알고 있는 독립 질의 N 개**를 요구합니다.
   그런 모양이 나오는 유일한 자리가 `_IDP_CHUNK` 루프인데, 그 루프는 정의부
   주석이 밝힌 대로 평시 1회로 끝납니다. ops 축이 "이미 보통 1회" 라고 스친
   사실의 일반형이며, **위험을 다 해결해도 배치할 것이 남지 않는다**는 뜻입니다.

### `ops_store` 질문에 대한 직답

**"ops_store 에만 넣으면 기존 코드를 안 고쳐도 되는가" 의 답은 세 문장입니다.**

- `ops_store/search.py` 에 `msearch` 메서드를 **추가하는 것 자체**는 기존 코드
  무변경으로 가능합니다. 모든 기존 메서드가 `search_raw` 로만 수렴하고 클래스가
  들고 있는 상태가 `client`·`default_index` 뿐이므로, 형제 메서드 하나가 늘어도
  기존 호출자의 동작은 바뀌지 않습니다.
- 그러나 **아무도 부르지 않으면 효과가 0** 이고, 부르게 하는 순간
  `_office_search.py` 의 진입점과 각 어댑터의 호출부, 그리고 사무실에서의
  `office.py` 재복사가 따라옵니다. 즉 "무변경" 은 **`ops_store` 안에서만
  참**이며, 질문이 겨냥한 "웹 애플리케이션을 안 고쳐도 되는가" 에 대한 답은
  **아니오** 입니다.
- 게다가 **자리가 틀렸습니다.** `ops_store` 는 vendored 사본이라 upstream
  `flask_modules` 와 동시에 고쳐야 하고, 다음 동기화에서 조용히 사라질 수
  있습니다. 넣어야 할 자리는 TRACKED 인 `_office_search.py` 이며, 그 안에서
  `client()` 위로 직접 부르면 vendored 사본을 건드리지 않습니다.

## 결론

| 질문 | 판정 |
| --- | --- |
| msearch 적용 시 운영에 무리가 없는가 | **지금 형태로는 무리가 있습니다.** 에러 시맨틱 역전 1건과 검증 사다리 재적용 1건이 BLOCKING 이며, 재시도 증폭이 harakiri 경계와 만나는 새 실패 모드가 생깁니다 |
| `ops_store` 에 넣으면 기존 코드 무변경인가 | **`ops_store` 안에서만 참입니다.** 효과를 내려면 `_office_search.py` 진입점 + 어댑터 호출부 + `office.py` 재복사가 따라옵니다 |
| 그래서 해야 하는가 | **아니오.** 위험을 전부 해결해도 배치할 독립 질의 집합이 남지 않습니다 |

어제 결정("계측만 출하한다")은 유지됩니다. 다만 두 축이 함께 짚었고 확인한
대로, **그 결정의 유일한 산출물인 요청별 소요시간 계측이 아직 출하되지
않았습니다** — `e65de1b8` 은 문서 108줄만 담았고 `_office_search.py` 에는
계측 코드가 없습니다. 다음 사무실 방문을 "측정 불가능한 변경 배포" 가 아니라
"판정에 쓸 데이터 획득" 으로 만들려면 그 계측이 먼저입니다.

## 축별 요약

- **운영 리스크 축**: 6건 (BLOCKING 2, MANAGEABLE 3, NOT-A-RISK 1). 최악은
  에러 시맨틱 역전 — 데이터 문제가 502 가 아니라 503 으로, 그것도 사용자가
  손댈 수 없는 메시지로 나갑니다.
- **표준 축**: 4건 (표준 2, smell 4). 최악은 vendored 사본 변경이나, 인용
  검증 결과 "금지" 가 아니라 "두 저장소 동시 변경" 으로 하향됩니다.
