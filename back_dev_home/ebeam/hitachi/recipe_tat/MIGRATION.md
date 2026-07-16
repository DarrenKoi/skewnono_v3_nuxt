# recipe_tat — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Shared: get_anchor_time()

- Called by `routes.py` before every endpoint to build an
  `AnalyticsRequestScope` (`_analytics_routes.resolve_analytics_scope`), which
  supplies the default `end_date` (anchor) / `start_date` (anchor − 30 days)
  when the caller omits them.
- Mock behavior: returns `ANCHOR_TIME`, a wall-clock timestamp captured once
  at process start (`datetime.now(timezone.utc)`), NOT a fixed mock date —
  the TAT dashboard's "last 30 days" default must always mean the real last
  30 days in every phase.
- Office data source: <!-- OFFICE: max(timestamp) over the real meas_hist index, not wall-clock -->
- Notes: per the module docstring, an office implementation must anchor on
  the real index's latest timestamp, not wall-clock `now()` — the two only
  coincide if the office index is fully up to date.

## Endpoint: GET /api/<tool_slug>/recipe-tat/ranking

- Handler: `routes.py` → `data.get_ranking(scope.tool_type, scope.fab_id,
  scope.start_date, scope.end_date, limit=scope.limit, lot_cd=scope.lot_cd)`.
  `tool_slug` (`cdsem`/`hvsem`) resolves to `ToolType` (`cd-sem`/`hv-sem`); an
  unrecognized slug short-circuits to a 400 before `data.py` is called.
- Contract: `list[RankingRow]` —

  ```python
  class RankingRow(TypedDict):
      rank: int
      class_name: str
      recipe_name: str
      full_name: str
      meas_counts: int
      total_meastime: int
      avg_meastime: float
      sample_lot_cds: list[str]
      sample_eqp_ids: list[str]
  ```

- Mock behavior: filters meas_hist rows in scope (`tool_type` / `fab_id` /
  date range / optional `lot_cd`), groups by `(class_name, recipe_name)`,
  sums `meastime` and execution counts per group, then ranks by
  `total_meastime` descending (ties keep dict-insertion order — not
  explicitly tie-broken). Truncated to `limit` (default 1000).
  `sample_lot_cds`/`sample_eqp_ids` are each capped to the first 5 distinct
  values (sorted), not the full set.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, terms aggregation on (class_name, recipe_name) with sum(meastime) + cardinality/top-hits sub-aggs -->
- Notes: `rank` is 1-indexed and reflects position after both sorting and
  `limit` truncation.

## Endpoint: GET /api/<tool_slug>/recipe-tat/summary

- Handler: `routes.py` → `data.get_summary(scope.tool_type, scope.fab_id,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`.
- Contract: `SummaryPayload` —

  ```python
  class SummaryPayload(TypedDict):
      tool_type: ToolType
      fab_id: str | None
      start_date: str | None
      end_date: str | None
      anchor_date: str
      total_tat_seconds: int
      total_recipes: int
      total_executions: int
      avg_meastime: float
  ```

- Mock behavior: sums `meastime` across rows in scope for `total_tat_seconds`,
  counts distinct `(class_name, recipe_name)` pairs for `total_recipes`, and
  divides for `avg_meastime` (`0.0` when there are zero executions — no
  division-by-zero error). `anchor_date` echoes `ANCHOR_TIME.date()`, not the
  requested `end_date`.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index aggregation (sum + cardinality) over the same bool filter as /ranking -->
- Notes: `anchor_date` is the date-picker ceiling, independent of whatever
  `start_date`/`end_date` the caller requested.

## Endpoint: GET /api/<tool_slug>/recipe-tat/daily-trend

- Handler: `routes.py` → `data.get_daily_trend(scope.tool_type, scope.fab_id,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`.
- Contract: `list[DailyTrendPoint]` —

  ```python
  class DailyTrendPoint(TypedDict):
      date: str
      total_meastime: int
      exec_count: int
  ```

- Mock behavior: buckets rows in scope by the date slice of `timestamp`
  (`YYYY-MM-DD`), summing `meastime`/counting executions per day, THEN
  backfills every calendar day between `start_date` and `end_date`
  (inclusive) with a zero-valued point so the trend chart has a continuous
  x-axis with no gaps. Sorted by `date` ascending.
- Office data source: <!-- OFFICE: OpenSearch date-histogram aggregation (daily interval) over the same bool filter, zero-filled for empty buckets -->
- Notes: the backfill only runs when both `start_date`/`end_date` parse as
  valid dates — an office adapter should preserve the same zero-fill
  guarantee so the frontend never has to special-case missing days.

## Endpoint: GET /api/<tool_slug>/recipe-tat/devices

- Handler: `routes.py` → `data.get_devices(scope.tool_type, scope.fab_id,
  scope.start_date, scope.end_date)` (no `lot_cd` — this endpoint enumerates
  the lot_cds, so it can't itself be scoped by one).
- Contract: `list[DeviceRow]` —

  ```python
  class DeviceRow(TypedDict):
      lot_cd: str
      exec_count: int
      total_meastime: int
      prod_catg_cd: str | None
      tech_nm: str | None
  ```

- Mock behavior: groups rows in scope by `lot_cd`, sums `meastime`/counts
  executions, joins in `prod_catg_cd`/`tech_nm` from `lot_metadata()` (R3
  lots carry `prod_catg_cd`, M-fab lots carry `tech_nm` — exactly one of the
  pair is populated per lot in practice). Sorted by `total_meastime`
  descending. Only lots with at least one measurement in scope are returned
  (no zero-count rows).
- Office data source: <!-- OFFICE: OpenSearch meas_hist index terms aggregation on lot_cd, joined with device/product metadata lookup -->
- Notes: drives the "디바이스별" quick-filter chip strip — an empty result is
  valid (no chips), not an error.

## Verify

    SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
