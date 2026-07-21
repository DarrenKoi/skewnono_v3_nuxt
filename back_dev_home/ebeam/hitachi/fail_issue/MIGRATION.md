# fail_issue — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.
- IMPORTANT: do NOT reimplement this by joining on recipe_tat's mock output.
  Read `align_fail` / `fail_ratio` / `msr_check` directly from the OpenSearch
  meas_hist index and perform the same aggregations (count, rate, daily
  series) natively. `MEAS_FAIL_THRESHOLD` (`0.15`) is pinned by the YAML
  contract (`docs/api-contracts/fail-issue.yaml`) — do not change its value,
  or Phase 1/2 numbers will disagree.

## Shared: get_anchor_time()

- Called by `routes.py` before every endpoint to build an
  `AnalyticsRequestScope` (`_analytics_routes.resolve_analytics_scope`), which
  supplies the default `end_date` (anchor) / `start_date` (anchor − 30 days)
  when the caller omits them.
- Mock behavior: returns the same `ANCHOR_TIME` recipe_tat uses (a wall-clock
  timestamp captured once at process start), since fail_issue's mock reuses
  recipe_tat's meas_hist row universe.
- Office data source: <!-- OFFICE: max(timestamp) over the real meas_hist index, not wall-clock -->
- Notes: office must anchor on the real index's latest timestamp, not
  wall-clock `now()`.

## Endpoint: GET /api/<tool_slug>/fail-issue/summary

- Handler: `routes.py` → `data.get_summary(scope.tool_type, scope.fab_name,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`. `tool_slug`
  (`cdsem`/`hvsem`) resolves to `ToolType`; an unrecognized slug short-circuits
  to a 400 before `data.py` is called.
- Contract: `SummaryPayload` —

  ```python
  class SummaryPayload(TypedDict):
      tool_type: ToolType
      fab_name: str | None
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
- Notes: `meas_fail_threshold` is echoed back verbatim (`0.15`) so the
  frontend can label the KPI without hard-coding it.

## Endpoint: GET /api/<tool_slug>/fail-issue/daily-trend

- Handler: `routes.py` → `data.get_daily_trend(scope.tool_type, scope.fab_name,
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
  scope.fab_name, scope.start_date, scope.end_date, limit=scope.limit,
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
  ```

- Mock behavior: groups rows in scope by `(class_name, recipe_name)`, counts
  executions and align-fails per group, DROPS groups with zero align-fails
  (this is a triage table, not a full recipe listing), then ranks by
  `(align_fail_count, align_fail_rate)` descending. Truncated to `limit`
  (default 1000). `sample_eqp_ids` is capped to the first 5 distinct sorted
  values.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, terms aggregation on (class_name, recipe_name) filtered to align_fail=="Fail", with a having-count>0 equivalent -->
- Notes: `rank` is 1-indexed post-truncation. A recipe with zero align fails
  never appears — an office adapter must apply the same drop, not return
  zero-count rows.

## Endpoint: GET /api/<tool_slug>/fail-issue/meas-ranking

- Handler: `routes.py` → `data.get_meas_ranking(scope.tool_type,
  scope.fab_name, scope.start_date, scope.end_date, limit=scope.limit,
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
  ```

- Mock behavior: same shape as `/align-ranking` but keyed on
  `fail_ratio > MEAS_FAIL_THRESHOLD` instead of `align_fail == "Fail"`, and
  additionally reports `avg_fail_ratio` (mean `fail_ratio` across ALL
  executions in the group, not just the failing ones). Groups with zero
  meas-fails are dropped; ranked by `(meas_fail_count, meas_fail_rate)`
  descending, truncated to `limit`.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, terms aggregation on (class_name, recipe_name) with avg(fail_ratio) + filtered count where fail_ratio > threshold -->
- Notes: `avg_fail_ratio` is over the full group, not the failing subset —
  do not average only the fail rows.

## Endpoint: GET /api/<tool_slug>/fail-issue/devices

- Handler: `routes.py` → `data.get_devices(scope.tool_type, scope.fab_name,
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

## Verify

    SKEWNONO_FAIL_ISSUE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue
