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
`timestamp` (the date range) and optionally one or more fabs. Text fields are
aggregated/filtered through their `.keyword` sub-fields (`text` is tokenized;
exact match / aggregation needs `.keyword`). Connection via `OPENSEARCH_HOST`
/ `OPENSEARCH_PORT` / `OPENSEARCH_USER` / `OPENSEARCH_PASSWORD` in
`back_dev_home/.env` (port defaults to 443/SSL).

Every `data.py`/provider function takes `fab_names: tuple[str, ...] | None`
(the multi-fab sidebar selection) rather than a single `fab_name: str |
None`. The shared `back_dev_home/ebeam/hitachi/_office_meas_hist.filter_clauses`
turns that tuple into the OpenSearch filter: one selected fab still emits a
single `term` clause on `fab_name.keyword` (byte-identical to the
pre-multi-fab query), and 2+ selected fabs emit one `terms` clause — a
**union** (여러 FAB 을 선택하면 합집합으로 집계됩니다), matching the mock's
case-insensitive "a row passes if `fab_name` matches ANY selected fab"
semantics. An empty tuple or `None` means no fab filter at all (fleet-wide).

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
  supplies the default `end_date` (anchor) / `start_date` (anchor − 14 days)
  when the caller omits them.
- Mock behavior: returns `ANCHOR_TIME`, a wall-clock timestamp captured once
  at process start (`datetime.now(timezone.utc)`), NOT a fixed mock date —
  the TAT dashboard's "last 14 days" default must always mean the real last
  14 days in every phase.
- Office data source: `max(timestamp)` aggregation across both aliases
  (`meas_hist_cdsem,meas_hist_hvsem`), parsed to an aware-UTC `datetime` and
  cached once per process (mirrors the mock pinning `ANCHOR_TIME` at import).
  Falls back to wall-clock `now()` only when neither alias has any rows.
- Notes: per the module docstring, an office implementation must anchor on
  the real index's latest timestamp, not wall-clock `now()` — the two only
  coincide if the office index is fully up to date.

## Endpoint: GET /api/<tool_slug>/recipe-tat/ranking

- Handler: `routes.py` → `data.get_ranking(scope.tool_type, scope.fab_names,
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

- Mock behavior: filters meas_hist rows in scope (`tool_type` / `fab_names`
  (union of the selected fabs) / date range / optional `lot_cd`), groups by
  `(class_name, recipe_name)`, sums `meastime` and execution counts per
  group, then ranks by
  `total_meastime` descending (ties keep dict-insertion order — not
  explicitly tie-broken). Truncated to `limit` only when `limit > 0`
  (default 0 = uncapped: every recipe in the date range is returned).
  `sample_lot_cds`/`sample_eqp_ids` are each capped to the first 5 distinct
  values (sorted), not the full set. (Office `sample_lot_cds` comes from a
  `lot_id` terms sub-agg mapped to lot_cds via the bridge; `sample_eqp_ids`
  from an `eqp_id.keyword` terms sub-agg.)
- Office data source: paginated `composite` aggregation on
  `full_name.keyword` (the `class_name/recipe_name` composite = the group
  key), walked page by page via `after_key` so **every** recipe in the range
  is covered, then sorted by `sum(meastime)` desc in Python. (A plain `terms`
  agg both truncates at its `size` cap and returns approximate sums when
  ordered by a sub-agg — unacceptable for fleet-wide ranges.) Per bucket:
  `doc_count` → `meas_counts`, `sum(meastime)` → `total_meastime`, a
  `top_hits` (size 1) recovers `class_name`/`recipe_name`/`full_name`, and a
  `terms` sub-agg on `eqp_id.keyword` (size 5, then sorted) fills
  `sample_eqp_ids`. `sample_lot_cds` comes from a `lot_id` terms sub-agg
  mapped through the `ebeam_tas_lot_hist` bridge; passing `lot_cd` resolves
  to a `lot_id` terms filter via the same bridge.
- Notes: `rank` is 1-indexed and reflects position after both sorting and
  `limit` truncation.

## Endpoint: GET /api/<tool_slug>/recipe-tat/summary

- Handler: `routes.py` → `data.get_summary(scope.tool_type, scope.fab_names,
  scope.start_date, scope.end_date, lot_cd=scope.lot_cd)`.
- Contract: `SummaryPayload` —

  ```python
  class SummaryPayload(TypedDict):
      tool_type: ToolType
      fab_names: list[str]
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

- Handler: `routes.py` → `data.get_daily_trend(scope.tool_type, scope.fab_names,
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

- Handler: `routes.py` → `data.get_devices(scope.tool_type, scope.fab_names,
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
  tool/fab/date scope (`sum(meastime)` + `doc_count`, paginated `composite`
  aggregation covering every in-scope lot — no top-N cap), map each
  `lot_id` to its `lot_cd` through the `ebeam_tas_lot_hist` bridge, and roll the
  per-lot sums up per device. `lot_id`s absent from the last-60-day bridge (i.e.
  not recently active) are dropped, keeping retired/unknown lots out. `tech_nm`
  is joined from the Redis `device_desc` catalog (`fac_id, lot_cd, stn_desc,
  chg_tm, tech_nm, rnd_connector`). `exec_count`/`total_meastime` are the real
  in-scope execution count and summed `meastime`; rows are ordered by
  `total_meastime` desc. `fab_names` filters via the shared `filter_clauses`
  helper (`term`/`terms` on `fab_name.keyword` — a union across 2+ selected
  fabs), same as the other endpoints. Metadata follows the mock's exactly-one rule:
  M-fab devices carry `tech_nm` (from `device_desc`), R3/R&D devices carry
  `prod_catg_cd` (from the Redis `r3_device_grp` DataFrame, `lot_cd →
  prod_catg_cd`).
- Notes: drives the "디바이스별" quick-filter chip strip — an empty result is
  valid (no chips), not an error.

## Endpoint: GET /api/<tool_slug>/recipe-tat/equipments

The office adapter is **not connected yet** — `providers/office_example.py` holds
an arity-only stub raising `NotImplementedError`. The composite aggregation that
fills it in is a separate task; this section records only what the office
implementer must check first. The contract (`EquipmentsPayload`, `EquipmentRow`,
`FleetReference`) is already in `contracts.py`.

Both providers MUST call
`providers/_shape.build_equipments_payload(tool_type, fab_names, start_date,
end_date, grid)` rather than aggregating themselves. The office side only builds
the grid — `(eqp_id, fab_name, eqp_model_cd, full_name, meas_counts,
total_meastime)` per (장비, 레시피) cell — and the shared assembler derives the
index, medians and percentiles. 두 provider 가 각자 계산하면 언젠가 숫자가
어긋나고, 그때 어느 쪽이 맞는지 판정할 방법이 없습니다.

- **OFFICE-VERIFY — does `tat_index` correlate with `fab_name`?** `tat_index` is
  an indirect standardization against `base(r)`, the per-recipe mean over the
  whole queried scope. If a recipe genuinely runs in several fabs at different
  rates, a multi-fab query blends them into `base(r)` and every tool in the
  slower fab reads slow — measuring the fab, not the tool. In the mock this is
  clearly visible (cd-sem, all fabs: M14 median index 1.13 at meastime ×1.25,
  M11 0.76 at ×0.74), but the mock's per-fab multiplier is fabricated, so it is
  no evidence about the real fleet. At the office, group `tat_index` by
  `fab_name` on a fleet-wide query and check for that correlation. **If it is
  present, `base(r)` should be computed per `(fab_name, recipe)` instead of
  scope-wide.** We are deliberately NOT making that change now — until the
  office numbers say otherwise, badge thresholds must be calibrated on a
  single-fab scope.
- **OFFICE-VERIFY — `TAT_INDEX_MIN_SAMPLE` (=12).** Tools with fewer executions
  in the window get `tat_index: None`. Check the real per-tool execution-count
  distribution: set too high, the column is all `—`; too low, noise gets a badge.
- **OFFICE-VERIFY — `eqp_model_cd.keyword`.** `docs/datatables/meas_hist.txt`
  records `eqp_model_cd` as `text`; whether the `.keyword` sub-field needed to
  aggregate on it exists is unconfirmed.

## Endpoint: GET /api/<tool_slug>/recipe-tat/equipment-compare

The office adapter is **not connected yet** — `providers/office_example.py` holds
an arity-only stub raising `NotImplementedError`. The contract
(`EquipmentComparePayload`, `EquipmentTrendSeries`, `EquipmentRecipeRow`,
`EquipmentRecipeCell`) is already in `contracts.py`.

- Called as `get_equipment_compare(scope.tool_type, scope.fab_names or None,
  scope.start_date, scope.end_date, scope.eqp_ids)`. No `lot_cd`: this view
  compares the tools the user checked in the `/equipments` table, and a device
  selection would silently narrow one column more than another.
- `scope.eqp_ids` is a **≤ 5 tuple** (`_analytics_routes.MAX_EQP_IDS`). The cap
  belongs to the request parser, not the contract, and the response echoes the
  list as actually used so truncation is visible rather than silent.
- `eqp_id` arrives **verbatim** — unlike `fab_name` it is not upper-cased,
  because it is an exact-match key for a `term`/`terms` query against
  `_office_meas_hist.EQP_ID_KW` (already used by `/ranking`'s `eqps` sub-agg).

Both providers MUST call
`providers/_shape.build_equipment_compare_payload(tool_type, fab_names,
start_date, end_date, eqp_ids, trend_rows, recipe_rows)`. The office side only
builds two grids on top of one `terms` filter over the selected `eqp_id`s:

| Grid | Tuple | Suggested aggregation |
| --- | --- | --- |
| `trend_rows` | `(eqp_id, date, total_meastime, exec_count)` | composite over `eqp_id.keyword` × `date_histogram(day)` |
| `recipe_rows` | `(eqp_id, full_name, meas_counts, total_meastime)` | composite over `eqp_id.keyword` × `full_name.keyword` |

The union of recipes, the zero-filled cells, the column order and the sort are
all the assembler's job. 사무실 어댑터가 "그 장비가 실제로 돈 레시피"만 격자에
넣어도 정상 동작합니다 — 나머지 칸은 조립기가 0으로 채웁니다. 반대로 격자를
미리 정렬하거나 열을 미리 맞출 필요는 없습니다.

- **`date` must be spelled `YYYY-MM-DD`.** The assembler indexes trend rows into
  a pre-built per-day bucket map (`_shape.days_in_range`), so a row whose date
  string does not match a day in the requested range is **dropped silently** —
  that is deliberate (it also discards out-of-range buckets), but it means a
  `date_histogram` returning epoch millis or `yyyy-MM-dd'T'HH:mm:ss` produces an
  all-zero chart with no error. Use `"format": "yyyy-MM-dd"` and read
  `key_as_string`, exactly as `/daily-trend` already does.
- Timestamps in `meas_hist_*` are KST stored as UTC (see
  `_office_meas_hist`), so the day boundaries here must match the ones
  `/daily-trend` and the date filter already use. A histogram with a different
  `time_zone` would put the same measurement on a different day than the
  `/equipments` table counts it on.
- **OFFICE-VERIFY — a tool with no rows in the window.** The frontend picks
  tools from `/equipments`, so every selected tool normally has data. The
  assembler still emits an all-zero series and zero cells for one that does not
  (the mock cannot produce that case; `tests/test_shape.py`'s `EQ-IDLE` pins the
  behaviour). Confirm the office aggregation simply returns no bucket for such a
  tool rather than failing the whole request.

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
