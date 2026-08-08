# fail_issue — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.
- IMPORTANT: do NOT reimplement this by joining on recipe_tat's mock output.
  `fail_ratio` is a PERCENTAGE (0..100) already computed at ingestion — read
  the stored field, never re-derive it from `fail_images` / `total_images`,
  and never rescale it. The rate fields (`align_fail_rate`, `meas_fail_rate`)
  are 0..1 fractions of rows; the two scales are not interchangeable.

  Read `align_fail` / `fail_ratio` / `msr_check` directly from the OpenSearch
  meas_hist index and perform the same aggregations (count, rate, daily
  series) natively. `MEAS_FAIL_THRESHOLD` (`15.0`, percent scale) is pinned by the YAML
  contract (`docs/api-contracts/fail-issue.yaml`) — do not change its value,
  or Phase 1/2 numbers will disagree.
- OpenSearch plumbing (client, composite walker, lot_id↔lot_cd bridge,
  device catalogs, shared anchor) lives in the TRACKED module
  `back_dev_home/ebeam/hitachi/_office_meas_hist.py` — recipe_tat's office
  adapter uses the same module, so after pulling this template both
  `office.py` copies (fail_issue AND recipe_tat) must be re-`cp`'d from
  their templates in the same deploy.
- Every `data.py`/provider function takes `fab_names: tuple[str, ...] | None`
  (the multi-fab sidebar selection) rather than a single `fab_name: str |
  None`. The shared `_office_meas_hist.filter_clauses` turns that tuple into
  the OpenSearch filter: one selected fab still emits a single `term` clause
  on `fab_name.keyword` (byte-identical to the pre-multi-fab query), and 2+
  selected fabs emit one `terms` clause — a **union** (여러 FAB 을 선택하면
  합집합으로 집계됩니다), matching the mock's case-insensitive "a row passes
  if `fab_name` matches ANY selected fab" semantics. An empty tuple or `None`
  means no fab filter at all (fleet-wide).

## Shared: get_anchor_time()

- Called by `routes.py` before every endpoint to build an
  `AnalyticsRequestScope` (`_analytics_routes.resolve_analytics_scope`), which
  supplies the default `end_date` (anchor) / `start_date` (anchor − 14 days)
  when the caller omits them.
- Mock behavior: returns the same `ANCHOR_TIME` recipe_tat uses (a wall-clock
  timestamp captured once at process start), since fail_issue's mock reuses
  recipe_tat's meas_hist row universe.
- Office data source: <!-- OFFICE: max(timestamp) over the real meas_hist index, not wall-clock -->
- Notes: office must anchor on the real index's latest timestamp, not
  wall-clock `now()`.

## Endpoint: GET /api/<tool_slug>/fail-issue/summary

- Handler: `routes.py` → `data.get_summary(scope.tool_type, scope.fab_names,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`. `tool_slug`
  (`cdsem`/`hvsem`) resolves to `ToolType`; an unrecognized slug short-circuits
  to a 400 before `data.py` is called.
- Contract: `SummaryPayload` —

  ```python
  class SummaryPayload(TypedDict):
      tool_type: ToolType
      fab_names: list[str]
      start_date: str | None
      end_date: str | None
      anchor_date: str
      total_executions: int
      align_fail_count: int
      align_fail_rate: float
      align_na_count: int
      meas_fail_count: int
      meas_fail_rate: float
      meas_fail_threshold: float
      distinct_equipment: int
      distinct_recipes: int
      distinct_lots: int
  ```

- Mock behavior: filters meas_hist rows in scope, counts `align_fail ==
  "Fail"` for `align_fail_count`, `align_fail == "NA"` for `align_na_count`,
  and `fail_ratio > MEAS_FAIL_THRESHOLD` for `meas_fail_count`. Rates are
  `count / total_executions`, `0.0` when `total_executions` is `0` (no
  division by zero). `distinct_equipment`/`distinct_recipes`/`distinct_lots`
  count unique `eqp_id` / `(class_name, recipe_name)` / `lot_cd` respectively.
  `anchor_date` echoes `ANCHOR_TIME.date()`, not the requested `end_date`.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index aggregation (filters + cardinality) over align_fail/fail_ratio -->
- Notes: `meas_fail_threshold` is echoed back verbatim (`15.0`) so the
  frontend can label the KPI without hard-coding it.

## Endpoint: GET /api/<tool_slug>/fail-issue/daily-trend

- Handler: `routes.py` → `data.get_daily_trend(scope.tool_type, scope.fab_names,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`.
- Contract: `list[DailyTrendPoint]` —

  ```python
  class DailyTrendPoint(TypedDict):
      date: str
      exec_count: int
      align_fail_count: int
      meas_fail_count: int
  ```

- Mock behavior: buckets rows in scope by the date slice of `timestamp`
  (`YYYY-MM-DD`), counting executions/align-fails/meas-fails per day, then
  backfills every calendar day between `start_date` and `end_date`
  (inclusive) with a zero-valued point so the trend chart has no gaps.
  Sorted by `date` ascending.
- Office data source: <!-- OFFICE: OpenSearch date-histogram aggregation (daily interval) with sub-filters for align_fail/meas_fail, zero-filled -->
- Notes: same zero-fill guarantee as recipe_tat's `/daily-trend` — only
  applies when both dates parse validly.

## Endpoint: GET /api/<tool_slug>/fail-issue/align-ranking

- Handler: `routes.py` → `data.get_align_ranking(scope.tool_type,
  scope.fab_names, scope.start_date, scope.end_date, limit=scope.limit,
  lot_cd=scope.lot_cd)`.
- Contract: `list[AlignRankingRow]` —

  ```python
  class AlignRankingRow(TypedDict):
      rank: int
      class_name: str
      recipe_name: str
      full_name: str
      exec_count: int
      align_fail_count: int
      align_fail_rate: float
      sample_eqp_ids: list[str]
      # Fabs whose measurements entered this aggregate, sorted asc
      # (multi-fab phase B, 2026-08-07). The detail link uses this to route
      # to the owning fab's registry (multi-fab spec §6.1).
      fab_names: list[str]
  ```

- Mock behavior: groups rows in scope by `(class_name, recipe_name)`, counts
  executions and align-fails per group, DROPS groups with zero align-fails
  (this is a triage table, not a full recipe listing), then ranks by
  `(align_fail_count, align_fail_rate)` descending. Truncated to `limit`
  (default 1000). `sample_eqp_ids` is capped to the first 5 distinct sorted
  values. `fab_names` is the group's distinct `fab_name` values, sorted —
  collected into the same per-group `set` the grouping already builds.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, terms aggregation on (class_name, recipe_name) filtered to align_fail=="Fail", with a having-count>0 equivalent -->
  `fab_names` comes from a sibling `terms` sub-agg on `fab_name.keyword`
  (size 16), placed on the recipe bucket **outside** the align-fail `filter`
  sub-agg — so it reports every fab that ran the recipe in scope, not only
  the fabs that failed. Bucket keys are `.upper()`-ed and sorted before
  returning; this is defensive, not a real normalization — `fab_name` is
  already stored uppercase (`_office_meas_hist.py`'s `filter_clauses`
  comment), so the call only guards a future writer that lowercases.
- Notes: `rank` is 1-indexed post-truncation. A recipe with zero align fails
  never appears — an office adapter must apply the same drop, not return
  zero-count rows.

## Endpoint: GET /api/<tool_slug>/fail-issue/meas-ranking

- Handler: `routes.py` → `data.get_meas_ranking(scope.tool_type,
  scope.fab_names, scope.start_date, scope.end_date, limit=scope.limit,
  lot_cd=scope.lot_cd)`.
- Contract: `list[MeasRankingRow]` —

  ```python
  class MeasRankingRow(TypedDict):
      rank: int
      class_name: str
      recipe_name: str
      full_name: str
      exec_count: int
      meas_fail_count: int
      meas_fail_rate: float
      avg_fail_ratio: float
      sample_eqp_ids: list[str]
      # Fabs whose measurements entered this aggregate, sorted asc
      # (multi-fab phase B, 2026-08-07). The detail link uses this to route
      # to the owning fab's registry (multi-fab spec §6.1).
      fab_names: list[str]
  ```

- Mock behavior: same shape as `/align-ranking` but keyed on
  `fail_ratio > MEAS_FAIL_THRESHOLD` instead of `align_fail == "Fail"`, and
  additionally reports `avg_fail_ratio` (mean `fail_ratio` across ALL
  executions in the group, not just the failing ones). Groups with zero
  meas-fails are dropped; ranked by `(meas_fail_count, meas_fail_rate)`
  descending, truncated to `limit`. `fab_names` is the group's distinct
  `fab_name` values, sorted, same as `/align-ranking`.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, terms aggregation on (class_name, recipe_name) with avg(fail_ratio) + filtered count where fail_ratio > threshold -->
  `fab_names` comes from the same sibling `terms` sub-agg on
  `fab_name.keyword` (size 16, outside the fail `filter` sub-agg, `.upper()`
  -ed and sorted) described under `/align-ranking` — both rankings share the
  recipe-bucket builder, so the sub-agg and its defensive `.upper()` are
  added once, not per endpoint.
- Notes: `avg_fail_ratio` is over the full group, not the failing subset —
  do not average only the fail rows.

## Endpoint: GET /api/<tool_slug>/fail-issue/devices

- Handler: `routes.py` → `data.get_devices(scope.tool_type, scope.fab_names,
  scope.start_date, scope.end_date)` (no `lot_cd` — this endpoint enumerates
  the lot_cds).
- Contract: `list[DeviceRow]` —

  ```python
  class DeviceRow(TypedDict):
      lot_cd: str
      exec_count: int
      align_fail_count: int
      meas_fail_count: int
      prod_catg_cd: str | None
      tech_nm: str | None
  ```

- Mock behavior: groups rows in scope by `lot_cd`, counts executions/align-
  fails/meas-fails, joins `prod_catg_cd`/`tech_nm` from `lot_metadata()` (R3
  lots carry `prod_catg_cd`, M-fab lots carry `tech_nm` — exactly one
  populated per lot in practice). Sorted by combined fail count
  (`align_fail_count + meas_fail_count`) descending, so the most-problematic
  devices surface first. Only lots with at least one measurement in scope
  are returned.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index terms aggregation on lot_cd with align/meas fail sub-filters, joined with device/product metadata lookup -->
- Notes: drives the "디바이스별" quick-filter chip strip — an empty result is
  valid (no chips), not an error.

## Endpoint: GET /api/<tool_slug>/fail-issue/equipments

- Handler: `routes.py` → `data.get_equipments(scope.tool_type, scope.fab_names,
  scope.start_date, scope.end_date)`. No `lot_cd` — same reason as `/devices`:
  this endpoint is the truth about which equipment exists in scope, so a
  device selection must not filter it.
- Contract: `EquipmentsPayload` (`EquipmentRow`, `FleetReference`) —

  ```python
  class EquipmentRow(TypedDict):
      eqp_id: str
      fab_name: str
      eqp_model_cd: str
      exec_count: int
      align_fail_count: int
      align_fail_rate: float          # fraction, 0..1
      align_expected: float
      align_index: float | None       # actual / expected, all-or-nothing null with the two below
      align_index_low: float | None   # Byar 95% lower bound
      align_index_high: float | None
      meas_fail_count: int
      meas_fail_rate: float
      meas_expected: float
      meas_index: float | None
      meas_index_low: float | None
      meas_index_high: float | None
      recipe_count: int
      top_recipe: str | None
      top_recipe_share: float         # share of EXEC COUNT, not meastime
  ```

- Mock behavior: folds `_filter_rows` output into an `(eqp_id, full_name)`
  grid — one cell per (equipment, recipe) pair the equipment actually ran in
  the window — then calls the shared assembler
  `providers/_shape.build_equipments_payload`. Fail counts use the same
  `_is_align_fail`/`_is_meas_fail` predicates as the other four endpoints, so
  a row that counts as an align-fail on `/align-ranking` counts the same way
  here.
- Office data source: **one** `composite` aggregation with **four** sources —
  `[eqp_id.keyword, fab_name.keyword, eqp_model_cd.keyword, full_name.keyword]`
  (named `eqp`/`fab`/`model`/`recipe`) — plus two `filter` sub-aggs
  (`align_fail == "Fail"`, `fail_ratio > MEAS_FAIL_THRESHOLD`). `fab_name`
  and `eqp_model_cd` ride along in the composite source instead of a
  per-bucket `top_hits`, because both are functionally dependent on
  `eqp_id` — adding them does not multiply the bucket count (여전히 장비
  수 × 레시피 수입니다). Do not "optimize" this into `top_hits` — reading one
  extra document per bucket is the expensive direction, not the cheap one.
- Both providers MUST call
  `providers/_shape.build_equipments_payload(tool_type, fab_names,
  start_date, end_date, grid)` rather than deriving `*_index`/medians/
  percentiles themselves. The index formula (indirect standardization,
  같은 기법을 recipe_tat 의 `tat_index` 도 씁니다) lives in exactly one place
  so mock and office numbers cannot quietly drift apart — 집에서는 office 를
  실행할 수 없으므로 어긋남을 잡을 심판이 애초에 없습니다.
- Notes: full field definitions and scales live in
  `docs/api-contracts/fail-issue.yaml`'s `EquipmentRow`/`FleetReference`
  types — this section intentionally does not repeat every field, only the
  aggregation shape and the shared-assembler rule.

## Endpoint: GET /api/<tool_slug>/fail-issue/equipment-compare

- Handler: `routes.py` → `data.get_equipment_compare(scope.tool_type,
  scope.fab_names, scope.start_date, scope.end_date, scope.eqp_ids)`.
  `scope.eqp_ids` is a **≤ 5 tuple** (`_analytics_routes.MAX_EQP_IDS`) — the
  cap belongs to the request parser, and the response echoes the list
  actually used (`eqp_ids`) so a truncation is never silent.
- Contract: `EquipmentComparePayload` (`EquipmentTrendSeries`,
  `EquipmentRecipeRow`, `EquipmentRecipeCell`) — see `contracts.py`.
- Mock behavior: folds the selected equipments' rows into two grids —
  `(eqp_id, date)` for the trend overlay and `(eqp_id, full_name)` for the
  recipe matrix — then calls `providers/_shape.build_equipment_compare_payload`,
  which owns the zero-fill for quiet days, the recipe union across selected
  equipments, the column order, and the sort.
- Office data source: 같은 필터에 `terms(eqp_id)` 를 더해 **두 번** walk 합니다.
  - 추이 격자는 `terms(eqp) × date_histogram(calendar_interval=day,
    format=yyyy-MM-dd)` 입니다 — **composite 가 아닙니다.**
    `_composite_sources` 는 (이름, 필드) 를 언제나
    `{"terms": {"field": ...}}` 로 감싸기 때문에, `timestamp` 를 composite
    소스로 주면 일 단위로 묶이지 않고 ns 정밀도 instant 마다 버킷이 하나씩
    생겨 조립기의 `"YYYY-MM-DD"` 칸과 하나도 맞지 않습니다 — 추이가 **예외
    없이 전부 0** 이 되고 빈 데이터와 구분되지 않습니다. 이 모듈에서
    `terms` 가 안전한 유일한 자리인 이유는 선택이 라우트에서 5개로 상한이
    걸려 있어(`MAX_EQP_IDS`) `size = len(selected)` 가 후보를 전부 덮기
    때문입니다 — 다른 집계가 composite 페이지네이션을 쓰는 이유(절단,
    서브집계 정렬 근사)가 여기서는 생기지 않습니다.
  - 레시피 격자는 `composite [eqp_id, full_name]` 입니다 — 레시피 수에
    상한이 없으므로 `terms` 로 바꾸면 잘린 레시피가 표에서 통째로
    사라지되 에러는 나지 않습니다.
- Both providers MUST call
  `providers/_shape.build_equipment_compare_payload(tool_type, fab_names,
  start_date, end_date, eqp_ids, trend_rows, recipe_rows)`. office 어댑터는
  선택 장비가 실제로 돈 레시피만 격자에 넣어도 됩니다 — 나머지 칸은
  조립기가 0 으로 채웁니다. 격자를 미리 정렬하거나 열을 미리 맞출 필요는
  없습니다.
- Notes: `date_histogram` 은 `format: "yyyy-MM-dd"` 를 주고 `key_as_string`
  을 그대로 읽습니다 — 문자열을 잘라 쓸 필요가 없습니다(`get_daily_trend`
  와 같은 방식). `min_doc_count: 0` + `extended_bounds` 로 조용한 날도
  버킷을 냅니다. 타임스탬프는 `meas_hist_*` 에서 KST 가 UTC 로 저장되어
  있으므로(`_office_meas_hist` 참고), 날짜 경계가 `/daily-trend` 및
  `/equipments` 와 어긋나지 않아야 같은 측정이 두 화면에서 다른 날짜로
  집계되는 일이 없습니다.

## 장비별 뷰 — office 어댑터가 해야 할 일

`office_example.py` 의 `get_equipments` / `get_equipment_compare` 두 함수를
그대로 `office.py` 에 옮기면 됩니다. 두 함수 모두 **자기 소스에서 격자만
만들고**, 지수·구간·중앙값·분위수 계산은 전부 `providers/_shape.py` 의 공용
조립기(`build_equipments_payload` / `build_equipment_compare_payload`)에
맡깁니다 — provider 가 이 계산을 직접 하면 mock 과 office 의 숫자가 언젠가
어긋나고, 집에서는 office 를 실행할 수 없으므로 그 어긋남을 잡을 방법이
없습니다.

## OFFICE-VERIFY 목록 (장비별 뷰)

집에서 정할 수 없는 것은 **셋뿐**입니다. 신뢰구간(Byar 근사)이 잡음 방어를
맡고 있어, 손으로 고를 상수가 recipe_tat 의 장비별 뷰보다 적습니다.

1. **`FAIL_INDEX_CEIL = 1.25` / `FAIL_INDEX_FLOOR = 0.75`**
   (`front-dev-home/app/utils/failEquipmentSignals.ts` — 이 파일은 아직
   없으며 뒤 태스크가 만듭니다. 경로만 미리 적어 둡니다.) 이 둘은 **통계
   추정이 아니라 업무 판단**입니다: 신뢰구간이 이미 잡음을 걸러내므로,
   이 상수를 잘못 잡아도 배지가 잡음 위에서 뜨는 일은 없고 다만 너무
   드물게 또는 너무 자주 뜰 뿐입니다. 조정 절차는
   `docs/superpowers/specs/2026-08-08-fail-issue-by-equipment-design.md`
   9.2절을 참고하십시오.
2. **`eqp_model_cd.keyword` 가 매핑에 존재하는가.** 없으면 composite 소스
   중 하나가 값 없는 문서를 전부 걸러내 **버킷이 0개**가 되고,
   `/equipments` 는 예외 없이 **200 에 빈 표**(`equipments: []`,
   `fleet.tool_count: 0`)를 돌려줍니다 — "이 기간에 데이터 없음"과 화면상
   구분되지 않습니다. 대처: 아래 "대조 절차"로 먼저 감지하고, 서브필드가
   없다면 `model` 소스를 빼고 버킷당 `top_hits`(size 1,
   `_source: ["eqp_model_cd"]`) 또는 sem_list 장비 카탈로그 조인으로
   모델을 되찾으십시오. **분석되는 raw `eqp_model_cd` 로 그냥 바꾸면
   안 됩니다** — 토큰화되어 `VERITYSEM_5` 가 `veritysem`/`5` 두 버킷으로
   쪼개진 채 모델명 행세를 하고, 이쪽도 에러 없이 조용히 틀립니다.
3. **다중 fab 편향이 사무실 데이터에서도 나타나는가.** 설계 3.1절이
   예측하는 대로, 여러 fab 을 함께 조회하면 지수가 장비가 아니라 fab 을
   가리킬 수 있습니다(mock 의 `FAB_ALIGN_FAIL_RATE`/`FAB_MEAS_FAIL_RATE`
   는 fab 별로 3배 차이가 나서 이 편향이 집에서 즉시 재현됩니다). fab
   없이 조회한 뒤 배지가 특정 fab 에 몰리는지 확인하십시오. 몰린다면
   예측대로이고, 프론트엔드가 이미 다중 fab 조회에서 배지를 끄므로
   (`isPeerGroupComparable`) 조치가 필요 없습니다. 몰리지 않는다면
   `base(r)` 를 fab 별로 계산할 필요가 없다는 뜻이므로, `_shape.py` 의
   관련 주석을 그때 정정하십시오.

**OFFICE-VERIFY 가 아닌 것:**

- `FAIL_INDEX_MIN_EXPECTED = 1.0` (`contracts.py`) — 기대 실패 건수가
  1건 미만이면 비율의 분모가 사실상 없다는 **정의의 경계**입니다. 튜닝
  대상이 아니므로 사무실 분포를 봐도 바뀔 이유가 없습니다.
- `CONFIDENCE_Z = 1.96` (`contracts.py`) — Byar 95% 신뢰구간의 **관례
  값**입니다. 통계 추정이 아니라 컨벤션이므로 이 역시 조정 대상이
  아닙니다.

차이는 "잡음 방어냐, 업무 판단이냐"입니다. 잡음 방어는 신뢰구간이 이미
맡고 있어 튜닝할 상수가 남지 않았고, 남은 것은 사람이 정하는 위 두
경계(`FAIL_INDEX_CEIL`/`FAIL_INDEX_FLOOR`)뿐입니다.

## 대조 절차 — office 스왑 직후 첫 실행에서 돌리는 것

새 픽스처 로스터가 없어 자동 형태 대조가 이 피처를 보지 않으므로(바로
아래 항목), 첫 실행에서는 이 대조를 손으로 돌립니다. 같은 tool/fab/기간의
`/equipments` 의 `fleet.total_executions` 가 `/summary` 의
`total_executions` 와 같은지 확인하십시오. office Flask 는 Phase 2 에서
`:5000` 으로 뜨고 홈은 `:5050` 을 씁니다 — 이미 그 포트가 점유돼 있을 수
있으므로, 비어 있는 포트를 `PORT=` 로 직접 지정해 띄우고 아래에서는
`<flask-host>`/`<port>` 자리를 실제 값으로 채우십시오.

```bash
BASE="http://<flask-host>:<port>"
curl -s "$BASE/api/cdsem/fail-issue/equipments?fab_name=<FAB>&start_date=<시작일>&end_date=<종료일>" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["fleet"]["total_executions"])'
curl -s "$BASE/api/cdsem/fail-issue/summary?fab_name=<FAB>&start_date=<시작일>&end_date=<종료일>" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["total_executions"])'
```

두 값이 다르면 composite 소스 중 하나가 문서를 떨어뜨리고 있다는 뜻이며,
가장 흔한 원인은 `eqp_model_cd.keyword` 미존재입니다(위 OFFICE-VERIFY
2번). `/summary` 는 composite 을 타지 않으므로 이 대조 하나로 네 소스
중 어느 것이든 값이 없는 문서를 걸러내는 문제를 잡을 수 있습니다.

## 가드 공백 — shape-drift 가드가 이 피처를 보지 않습니다

`fail_issue` 는 `scripts/capture_fixtures.py` 의 `ENDPOINTS` 로스터에
**한 항목도 없고**, `__fixtures__` 디렉터리도 없습니다. 이는 이번에
추가한 두 엔드포인트만이 아니라 **기존 다섯 개
(`summary`/`daily-trend`/`align-ranking`/`meas-ranking`/`devices`)에도
해당**됩니다. 즉 `scripts/check_contract.py` 의 mock↔office 형태 대조가
이 피처를 전혀 보지 않으며, 그 결과는 CI/스크립트 출력에서 "문제 0건"으로
읽히지 "검사 안 함"으로 읽히지 않습니다 — 로스터가 조용하다고 안심하면
안 됩니다.

office 스왑 직후에는 위 "대조 절차"를 손으로 대신 돌리십시오. 로스터에
항목을 채우려면 실행 중인 Flask 로 픽스처를 캡처해야 하고, 그러면 기존
다섯 엔드포인트까지 함께 끌어들이는 별개의 작업이 됩니다 — 이번 변경
범위 밖입니다.

## Verify

    SKEWNONO_FAIL_ISSUE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue
