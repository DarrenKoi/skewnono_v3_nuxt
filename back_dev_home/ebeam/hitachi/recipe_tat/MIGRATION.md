# recipe_tat — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Data source: OpenSearch `meas_hist_*` (+ pending Redis lot map)

Measurement history lives in the office **OpenSearch** cluster (via
`ops_store`, `opensearch-py`), one alias per tool family:

- `meas_hist_cdsem` — `tool_type == "cd-sem"`
- `meas_hist_hvsem` — `tool_type == "hv-sem"`

The adapter never pulls raw rows — every endpoint is a **server-side
aggregation** over `meastime` (per-execution TAT, seconds) sliced by
`timestamp` (the date range) and optionally `fab_name`. Text fields are
aggregated/filtered through their `.keyword` sub-fields (`text` is tokenized;
exact match / aggregation needs `.keyword`). Connection via `OPENSEARCH_HOST`
/ `OPENSEARCH_PORT` / `OPENSEARCH_USER` / `OPENSEARCH_PASSWORD` in
`back_dev_home/.env` (port defaults to 443/SSL).

**`lot_cd` is NOT a meas_hist field** (and `lot_id` does not encode it). The
**bridge** is OpenSearch `ebeam_tas_lot_hist`, which carries both `lot_id` and
`lot_cd` (its `lot_id` matches meas_hist's) — pulled as a last-60-day frame and
cached. It powers three things:

- `/devices` — aggregate meas_hist by `lot_id` in scope → map to `lot_cd` →
  roll up (also needs Redis `device_desc` for `tech_nm`; see below).
- the `lot_cd` drill-down on ranking / summary / daily-trend — `lot_cd` → its
  `lot_id` set → `terms(lot_id.keyword)` filter (`_lot_ids_for_lot_cd`).
- `sample_lot_cds` on ranking rows — a `lot_id` terms sub-agg mapped to lot_cds
  (wrapped so a lot-history hiccup degrades it to `[]` without breaking ranking).

The OpenSearch-native paths (summary, daily-trend, core ranking, anchor) still
work without the bridge; the contract gate never passes `lot_cd`.

## Shared: get_anchor_time()

- Called by `routes.py` before every endpoint to build an
  `AnalyticsRequestScope` (`_analytics_routes.resolve_analytics_scope`), which
  supplies the default `end_date` (anchor) / `start_date` (anchor − 30 days)
  when the caller omits them.
- Mock behavior: returns `ANCHOR_TIME`, a wall-clock timestamp captured once
  at process start (`datetime.now(timezone.utc)`), NOT a fixed mock date —
  the TAT dashboard's "last 30 days" default must always mean the real last
  30 days in every phase.
- Office data source: `max(timestamp)` aggregation across both aliases
  (`meas_hist_cdsem,meas_hist_hvsem`), parsed to an aware-UTC `datetime` and
  cached once per process (mirrors the mock pinning `ANCHOR_TIME` at import).
  Falls back to wall-clock `now()` only when neither alias has any rows.
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
  values (sorted), not the full set. (Office `sample_lot_cds` comes from a
  `lot_id` terms sub-agg mapped to lot_cds via the bridge; `sample_eqp_ids`
  from an `eqp_id.keyword` terms sub-agg.)
- Office data source: `terms` aggregation on `full_name.keyword` (the
  `class_name/recipe_name` composite = the group key), ordered by
  `sum(meastime)` desc, `size = limit`. Per bucket: `doc_count` → `meas_counts`,
  `sum(meastime)` → `total_meastime`, a `top_hits` (size 1) recovers
  `class_name`/`recipe_name`/`full_name`, and a `terms` sub-agg on
  `eqp_id.keyword` (size 5, then sorted) fills `sample_eqp_ids`.
  `sample_lot_cds` stays `[]` until the Redis lot_cd source is wired.
  Passing `lot_cd` resolves to `lot_id` terms via the (pending) Redis map.
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
- Office data source: a single aggregation over the same `bool.filter` as
  /ranking — `sum(meastime)` → `total_tat_seconds`, `value_count(meastime)`
  → `total_executions` (every doc has `meastime`), `cardinality(full_name.keyword)`
  → `total_recipes` (exact at this cardinality). `avg_meastime` = `sum/count`
  (`0.0` when count is 0 — no div-by-zero). `anchor_date` echoes
  `get_anchor_time().date()`, independent of the requested `end_date`.
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
- Office data source: a `date_histogram` on `timestamp` (`calendar_interval:
  day`, `format: yyyy-MM-dd`, UTC) with a `sum(meastime)` sub-agg over the same
  `bool.filter`. `min_doc_count: 0` + `extended_bounds` (`start_date`..`end_date`)
  zero-fills every empty calendar day, giving the same continuous x-axis the
  mock backfills. Buckets come back date-ascending.
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
- Office data source: aggregate meas_hist_* by `lot_id.keyword` within the
  tool/fab/date scope (`sum(meastime)` + `doc_count`, top 5000 by TAT), map each
  `lot_id` to its `lot_cd` through the `ebeam_tas_lot_hist` bridge, and roll the
  per-lot sums up per device. `lot_id`s absent from the last-60-day bridge (i.e.
  not recently active) are dropped, keeping retired/unknown lots out. `tech_nm`
  is joined from the Redis `device_desc` catalog (`fac_id, lot_cd, stn_desc,
  chg_tm, tech_nm, rnd_connector`). `exec_count`/`total_meastime` are the real
  in-scope execution count and summed `meastime`; rows are ordered by
  `total_meastime` desc. `fab_id` filters via `fab_name.keyword` (fine-grained,
  same as the other endpoints).
  PENDING: the R3/R&D `prod_catg_cd` source — the mock uses `r3_device_grp`, so
  if that DataFrame is in office Redis too, R3 rows can populate `prod_catg_cd`
  (currently `None`).
- Notes: drives the "디바이스별" quick-filter chip strip — an empty result is
  valid (no chips), not an error.

## Verify

Standalone smoke test (prints anchor + per-tool summary/ranking/trend;
loads `.env` itself, needs OpenSearch reachable):

    .venv/bin/python -m back_dev_home.ebeam.hitachi.recipe_tat.providers.office

Contract gate (`.env` loaded by `back_dev_home/conftest.py`):

    SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat

Both run from the repo root. All four contract cases should pass once
OpenSearch (`meas_hist_*` + `ebeam_tas_lot_hist`) and Redis (`device_desc`) are
reachable and populated. `test_get_devices` exercises the full bridge
(meas_hist agg → lot_id→lot_cd map → device_desc join), so it needs both
`OPENSEARCH_*` and `REDIS_*` set.
