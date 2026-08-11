# device_statistics — office migration

## Status (2026-07-31)

`providers/office_example.py` is **implemented, not yet office-verified.** All
five functions are written against the real sources; `cp office_example.py
office.py` at the office and run the Verify command at the bottom.

주차 스냅샷 스케줄러는 이제 존재합니다(`back_dev_home/_scheduler/`). 월요일
01:00 에 `write_weekly_snapshot()`, 02:30 에 `sweep_weekly_snapshots()` 가
돕니다. 사무실에서는 `cp office_example.py office.py` 만 하면 켜집니다.

One fact is easy to re-break: **`skip_yn` — `"Y"` means skipped, and the field
has THREE values** (`"Y"`, `"N"`, and blank). Selecting measured steps is
`!= "Y"`, never `== "N"` — the latter silently drops every blank-valued step.
Both the adapter and the mock funnel this through one `_is_measuring()`.

The remaining OFFICE-VERIFY items are listed in the adapter's module
docstring.

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `providers/snapshot_store.py`, `providers/statistics.py`,
  `providers/recipe_params.py`, `providers/rules.py`, `contracts.py`, or
  `tests/`. (`data.py` 는 2026-08-01 에 스케줄러 진입점 두 개가 추가되면서 한 번
  바뀌었습니다 — dispatcher 에 함수를 더한 것이며 `_provider()` 선택 로직은
  그대로입니다. 사무실 방문에서는 여전히 건드리지 않습니다.)
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.
- Implement **all five** functions here: `get_r3_device_grp`,
  `get_device_desc`, `get_recipe_params`, `get_weekly_trend_data`,
  `get_rules`. These back six GET endpoints (`recipe-statistics` and
  `recipe-trend` both call `get_weekly_trend_data`, just with different
  arguments and different route-level post-processing).
- **일곱 개**를 구현합니다: 기존 다섯 개에 더해 `write_weekly_snapshot`,
  `sweep_weekly_snapshots`. 뒤의 두 개는 스케줄러가 부르며 화면이 부르지
  않습니다.
- **External importer — do not break this.** `back_dev_home/ebeam/_analytics.py`'s `lot_metadata()` lazily imports `get_device_desc` and
  `get_r3_device_grp` from `device_statistics.data` (the switch you are
  implementing here) — it powers Recipe TAT's device quick-filter chips.
  Once office is selected, `lot_metadata()` will read office data
  automatically; make sure `get_device_desc()`/`get_r3_device_grp()` keep
  returning the same row shapes (`lot_cd`, `fac_id`, `prod_catg_cd`,
  `tech_nm` are the fields it actually reads).
- **Do NOT touch `providers/mock.py`'s `_lot_index` export or the recipe_tat
  import that reads it.** `back_dev_home/ebeam/recipe_tat/providers/mock.py` imports `_lot_index` directly from
  `device_statistics.providers.mock` — NOT from `device_statistics.data` —
  by design. That import intentionally bypasses this office switch: Recipe
  TAT's own mock provider needs a mock lot pool regardless of which
  provider device_statistics itself is running, since Recipe TAT has no
  office adapter of its own here. Nothing in this office migration should
  change that import path.

## Endpoint: GET /api/cdsem/device-statistics/r3-device-grp

- Handler: `routes.py` → `r3_device_grp()` → `data.get_r3_device_grp()`, no
  query params.
- Contract: `list[R3DeviceGrpRow]` —

  ```python
  class R3DeviceGrpRow(TypedDict):
      id: str
      fac_id: str
      plan_catg_type: str
      prod_catg_cd: str
      tech_cd: str
      den_type: str
      prod_grp_typ: str
      gen_typ: str
      lot_cd: str
      plan_grade_cd: str
      lake_load_tm: str
      ctn_desc: str
  ```

- Mock behavior: a fixed, memoized (`lru_cache`) universe of 2000 rows
  generated once per process, all with `fac_id: "R3"` and unique
  `lot_cd`/`id` values (`R{base36 index}` / `R3-####`). Deterministic per
  process via a fixed RNG seed (`20260426`) — the same rows every call
  within a process, not necessarily byte-identical across process restarts
  if the generator changes, but stable within a running server.
- Office data source: Redis `r3_device_grp` (parquet DataFrame). Columns map
  1:1 except `plan_catg_typ`→`plan_catg_type` and `den_typ`→`den_type`; `id`
  has no source column and is synthesized as `{fac_id}-{lot_cd}` (a row index
  would move every device's id whenever the catalog changes). See
  `docs/datatables/r3_device_grp.txt`.
- Notes: **this endpoint has no query params** — unlike
  `recipe-statistics`/`recipe-params`/`recipe-trend` below, there is no
  lot-narrowing here to preserve. `lot_cd` is the join key shared with
  `device-desc` below — office must keep both tables' `lot_cd` vocabularies
  compatible for `recipe-params`/`recipe-statistics`/`recipe-trend`'s
  downstream lot lookups to work at all.
- Office activity filter (user-confirmed 2026-08-04): the office adapter
  intersects the catalog with the unique `lot_cd` set from the last 90 days
  of `ebeam_tas_lot_hist` (`_active_lot_cds`, same window as the M-fab step
  query) so the picker only lists devices with recent measurement activity —
  the raw catalog still contains retired lots. The mock does NOT stand in
  for this filter (it cannot know which lots are genuinely recent) and
  returns the full universe; only the office adapter narrows. OFFICE-VERIFY:
  confirm R3 lot codes actually appear in `ebeam_tas_lot_hist.lot_cd` (the
  recipe_tat adapter joins the same set against `r3_device_grp`, so they
  should).

## Endpoint: GET /api/cdsem/device-statistics/device-desc

- Handler: `routes.py` → `device_desc()`. Reads `fac_id` from the query
  string as a comma-separated list (`?fac_id=M11,M10`), splits and strips
  it, then calls `data.get_device_desc(fac_ids)` (empty list becomes
  `None`, meaning "no filter").
- Contract: `list[DeviceDescRow]` —

  ```python
  class DeviceDescRow(TypedDict):
      id: str
      fac_id: str
      lot_cd: str
      ctn_desc: str
      chg_tm: str
      tech_nm: str
      rnd_connector: str
  ```

- Mock behavior: a fixed, memoized 2000-row universe (400 rows per fab)
  spread across `M10`/`M11`/`M14`/`M15`/`M16`, generated once with RNG seed
  `20260427` independently of `r3_device_grp` — `rnd_connector` (the R&D
  code name a device carried pre-mass-production) is deliberately NOT
  derived from any r3_device_grp field, matching real-world data
  provenance (~90% of rows get a non-empty `rnd_connector`, ~10% get `""`).
  When `fac_ids` is provided, filtering is by exact (normalized-uppercase)
  `fac_id` match; an empty/all-falsy `fac_ids` list (after stripping)
  behaves identically to `None` — full unfiltered table.
- Office data source: Redis `device_desc` (parquet DataFrame), filtered by
  uppercase `fac_id`. The description column is `ctn_desc`, with `stn_desc`
  accepted as a fallback since that name has been recorded both ways. `id` is
  synthesized as `{fac_id}-{lot_cd}` like `r3-device-grp` above. See
  `docs/datatables/device_desc.txt`.
- Notes: like `r3-device-grp`, this endpoint returns the full (or
  fac_id-filtered) table with no lot-narrowing — no huge-payload concern
  here relative to the trend/params endpoints below, but the unfiltered
  call is still ~2000 rows; office does not need to artificially cap it.
  The same 90-day `ebeam_tas_lot_hist` activity filter as `r3-device-grp`
  applies office-side (user-confirmed 2026-08-04, see the note there).

## Endpoint: GET /api/cdsem/device-statistics/meas-activity

- Handler: `routes.py` → `meas_activity()`. Requires `fac_id` (400 without
  it, same policy as `rules` — a ranking without a fab axis is meaningless).
  Calls `data.get_meas_activity(fac_id)`.
- Contract: `list[MeasActivityRow]` (`{lot_cd, meas_count}`), **sorted by
  `meas_count` descending** — the contract promises the order because the
  frontend's 측정 상위 N quick filter takes the first N entries after
  intersecting with the visible catalog. An unknown fab returns `[]`, never
  another fab's ranking.
- Mock behavior: deterministic per-lot fake counts (hash of `lot_cd`,
  pressed into a heavy tail — a few busy devices, a long quiet tail) over
  the fab's catalog lots. Absolute values are fabricated; only the ranking
  behavior is being stood in for.
- Office data source: the same `ebeam_tas_lot_hist` terms aggregation as
  `_active_lot_cds`, narrowed by `fab_id` term + 90-day `event_tm` range;
  `doc_count` per `lot_cd.keyword` bucket is the measurement count
  (`ebeam_tas_lot_hist.txt` activity-count usage). OFFICE-VERIFY: confirm
  R3 documents carry `fab_id="R3"` — if not, R3 ranks come back empty and
  the 측정 상위 filter silently blanks the R3 table only.

## Endpoint: GET /api/cdsem/device-statistics/recipe-statistics

- Handler: `routes.py` → `recipe_statistics()`. Reads `lot_cds` from the
  query string (comma-separated, e.g. `?lot_cds=R000,R001`), calls
  `data.get_weekly_trend_data(lot_cds or None)` (defaults: `points=8`,
  `interval_days=7`, `include_recipes=True`), then takes ONLY the latest
  date's bucket from the returned dict and reshapes it to
  `{"date": <iso>, "buckets": <TrendBucket>}` — an empty trend dict becomes
  `{"date": None, "buckets": {}}`.
- Contract (of `get_weekly_trend_data` itself — the wire response is a
  route-level reshape of this, not a separate data-layer shape):

  ```python
  class TrendBucket(TypedDict, total=False):
      all_rcp_info: list[RecipeInfoRow]
      all_summary: list[SummaryRow]
      only_normal_rcp_info: list[RecipeInfoRow]
      only_normal_summary: list[SummaryRow]
      mother_normal_rcp_info: list[RecipeInfoRow]
      mother_normal_summary: list[SummaryRow]
      only_sample_rcp_info: list[RecipeInfoRow]
      only_sample_summary: list[SummaryRow]

  # get_weekly_trend_data(...) -> dict[str, TrendBucket]  (ISO date -> bucket)
  ```

  `RecipeInfoRow`/`SummaryRow` are the per-recipe and per-lot-aggregate row
  shapes — see `contracts.py` for the full field lists (22 and 17 fields
  respectively; both carry the five ranged `para_*` counts plus their
  `_percent` siblings — `para_buckets.py` owns the boundaries).
- Mock behavior: buckets recipes into 4 categories per lot per date
  (`all`, `only_normal`, `mother_normal`, `only_sample`), each with its own
  recipe-count range (widest for `all`, narrowest for `only_sample`), and
  pairs each `*_rcp_info` list with a `*_summary` aggregate row. Generation
  is deterministic per `(lot_cd, date_index)` via `_seed_for` — repeated
  calls with the same lot/date give byte-identical output. `points`/
  `interval_days` govern how many weekly dates are generated (always the
  full window is built, then only the latest is surfaced by this route) —
  **do not change `points` from its default**: `_seed_for` keys off
  `point_index`, so reducing `points` shifts which index is "latest" and
  changes that date's generated values, breaking the deterministic-per-date
  guarantee documented on `get_weekly_trend_data`.
- **A `RecipeInfoRow` is a step, not a recipe.** Its identity is
  `(oper_seq, samp_seq)` — the identity of one `sknn-planstep-r3` document.
  `recipe_id` repeats within a lot because several steps run the same
  measurement recipe, so it is a join key only; keying rows or UI lists on it
  silently collapses steps. The mock reproduces the reuse
  (`recipe_population.SHARED_RECIPE_RATIO`, ~4% of steps), and steps sharing a
  recipe carry an identical `para_*` block because office derives those counts
  from the recipe's parameters, not from the step.
- Office data source: the **latest** weekly point is computed live from the
  step sources (R3 `sknn-planstep-r3` by `prod_id = lot_cd + "_BASE"`, M-fab
  `ebeam_tas_lot_hist` over the last 90 days), joined to `cdsem_idp_ver` for
  each recipe's newest `parameters` blob. Because this route only ever reads
  the latest date, it never touches the weekly snapshots. Bucket membership
  (all / only_normal / mother_normal / only_sample) is derived from the step
  name, the recipe name, and — for `mother_normal` only — the per-parameter
  mother flag. See `docs/datatables/planstep_r3.txt` "화면의 네 버킷" and the
  **mother_para 출처** section at the end of this file.
- Notes: **huge-payload endpoint.** Called with no `lot_cds` filter, this
  fans out over every lot in the mock (2000 R3 + 2000 M-fab = 4000 lots)
  and returns a full cross-product — this is how the original capture
  produced a 1.07 GB golden file before the parity harness pinned it down
  to a single lot. The frontend
  (`front-dev-home/app/composables/useRecipeStatisticsApi.ts`) always joins
  a user-selected lot list into `lot_cds` before calling; an unfiltered
  call is not a realistic usage pattern. The parity harness pins
  `?lot_cds=R000` (a real R3 lot, ~165 KB response) — office's realistic
  per-request size for the documented, expected usage (a handful of
  user-selected lots) should stay in the tens-to-low-hundreds of KB range,
  not the multi-GB unfiltered case.

## Endpoint: GET /api/cdsem/device-statistics/recipe-params

- Handler: `routes.py` → `recipe_params()`. Reads `lot_cds` from the query
  string (comma-separated), calls
  `data.get_recipe_params(lot_cds or None)` and returns the flat list
  directly (no route-level reshape).
- Contract: `list[RecipeParamsRow]` —

  ```python
  class ParameterRow(TypedDict):
      name: str
      point_count: int

  class RecipeParamsRow(TypedDict):
      lot_cd: str
      recipe_id: str
      fac_id: str
      ctn_desc: str
      prod_catg_cd: str
      recipe_class: Literal["Main", "Sample"]
      family: Literal["Core", "Pool", "VG_RTC_Cubic"]
      phase: Literal["t-EV", "EV", "TV", "PV"] | None
      memory_class_auto: Literal["DRAM", "NAND", "unknown"]
      parameters: list[ParameterRow]
  ```

- Mock behavior: 100–200 recipes per requested lot (`RECIPE_COUNT_RANGE`),
  deterministic per lot via a seeded RNG (`_seed_for(lot_cd, 4242)`).
  `prod_catg_cd` is reused from the lot's own `r3_device_grp` row when it
  is an R3 lot; M-fab `device_desc` rows carry no `prod_catg_cd`, so it
  falls back to a deterministic pick. `memory_class_auto` is derived
  purely from `prod_catg_cd` (`DRAM`→`DRAM`, `NAND`/`FLASH`→`NAND`,
  anything else→`unknown`, meaning manual classification per D7). ~8% of
  recipes are deliberately "bloated" (many extra `OTHER`-type parameters)
  and ~5% deliberately carry a point-count outlier (one `EDGE_R` parameter
  pushed to 40–60 points) — these are intentional signal, not noise, so
  both the outlier-detection view and R3 compliance checks have real data
  to validate against. Parameter names are chosen from fixed per-type
  pools (`WAFER_*`, `LEVEL_*`, `EDGE_*`, `EDGE_EX_*`, plus an `OTHER` bag)
  specifically to exercise the frontend's longest-prefix type derivation
  (`EDGE_EX` > `EDGE` > `WAFER` > `LEVEL` > everything else = `OTHER`).
- Office data source: the same step sources as `recipe-statistics`, one row
  per distinct `recipe_id`, with `parameters` from `cdsem_idp_ver`'s newest
  version. The mock matches that grain: it walks the step population but
  emits the first row per `recipe_id` only, so a recipe reused by two steps
  still has exactly one parameter set — `cdsem_idp_ver` holds one blob per
  `full_name`. `recipe_class` / `family` / `phase` / `memory_class_auto` are
  derived, not stored — the derivation table is in
  `docs/datatables/recipe_params.txt` "사무실 파생 규칙".
- Notes: **huge-payload endpoint**, same shape of concern as
  `recipe-statistics` above — an unfiltered call fans out over all ~4000
  lots (the original capture was 578 MB). The parity harness pins
  `?lot_cds=R000` (~100 KB). The frontend
  (`front-dev-home/app/composables/useDeviceStatisticsApi.ts`) always
  passes a selected lot list. `lot_cd`/`fac_id` here must stay joinable
  with `r3-device-grp`/`device-desc`'s own `lot_cd`/`fac_id` columns.

## Endpoint: GET /api/cdsem/device-statistics/rules

- Handler: `routes.py` → `measurement_rules()`. Requires `fab` as a query
  param (`400 invalid_request`-equivalent `abort(400)` if missing/blank —
  via Flask's `abort`, not the project's `error_json` helper, so the error
  body shape differs from other 4xx responses in this codebase). Calls
  `data.get_rules(fab)`; a `None` result is translated to `abort(404)` by
  the route itself, not by `data.py`/the provider.
- Contract: `RuleVersion` —

  ```python
  class NameOverride(TypedDict):
      patterns: list[str]
      match: Literal["contains", "affix"]
      cap: int | None  # None = exempt (unlimited)

  class Selector(TypedDict, total=False):
      fab: str                                    # required (see SelectorBase)
      recipe_class: Literal["Main", "Sample"]      # required (see SelectorBase)
      family: Literal["Core", "Pool", "VG_RTC_Cubic"]
      phase_in: list[str]
      yield_check: Literal["before", "after"]
      memory_class: Literal["DRAM", "NAND"]

  class RuleCell(TypedDict):
      id: str
      selector: Selector
      caps: dict[str, int]        # WAFER/LEVEL/EDGE/EDGE_EX/_other
      name_overrides: list[NameOverride]

  class Thresholds(TypedDict):
      yellow_at: float
      red_at: float

  class RuleVersion(TypedDict):
      fab: str
      version: int
      edited_by: str
      edited_at: str
      cells: list[RuleCell]
      thresholds: Thresholds
  ```

  (`fab`/`recipe_class` on `Selector` are structurally required — modeled
  as `SelectorBase` in `contracts.py` with `Selector` extending it via
  `total=False` for the remaining optional keying axes — see
  `contracts.py` for the exact split.)
- Mock behavior: a single seeded rule version for fab `"R3"` only
  (`version: 1`) covering the full family × (phase | yield_check) ×
  memory_class matrix for `Main` recipes plus `Sample` rules keyed by
  memory_class. Any other `fab` value returns `None`. **Backend serves raw
  rule cells only** — violation judgment and traffic-light coloring are
  computed client-side by the frontend's `ruleEngine.ts` (§8-bis
  principle); this endpoint never evaluates or filters against real
  parameter data. Cell match order matters: `r3-sample-core-tvpv` must
  precede the general `r3-sample-dram`/`r3-sample-nand` cells so the
  frontend's first-match selection picks the more specific cell.
- Office data source: **none — the office adapter returns the same in-code
  seed (`providers/rules.py`) as the mock.** In-app rule editing will not be
  built (decided 2026-08-04): rule changes are made by editing `rules.py`
  and deploying, so git history is the version history and the two
  providers can never diverge. The earlier design (publish to the Redis
  hash `v3_device_statistics_rules`, seeded by a script) was discarded —
  it bought nothing without a save path and produced a 404 for every fab
  until someone remembered to publish (which is exactly what happened
  office-side on 2026-08-04). `fac_id` values without a seed entry still
  404, by contract.
- Notes: not a huge-payload endpoint — one fab's rule set is a handful of
  cells.
- Troubleshooting — **comparison page shows 판정 범위 `0 / N` for every R3
  lot**. Two known causes, told apart by the coverage-cell tooltip:
  1. `rules?fac_id=R3` returns 404 (tooltip: "계측 룰이 없습니다") — with
     the current adapter this can only be a **stale `office.py`** still
     reading the discarded Redis hash. Refresh it:
     `python -m scripts.sync_office_adapters device_statistics`.
  2. Rules load but every recipe falls out as gray (e.g. `phase` is
     null because real device `ctn_desc` strings don't carry parseable
     EV/TV/PV tokens, or `memory_class` is unknown and Pool lots lack a
     `yield_check` annotation). The tooltip lists the per-reason gray
     counts ("룰은 있으나 전 recipe 가 판정에서 제외 — …") so the blocking
     derivation can be identified on the spot.

## Endpoint: GET /api/cdsem/device-statistics/recipe-trend

- Handler: `routes.py` → `recipe_trend()`. Reads `lot_cds` (comma-separated),
  `start_date`, `end_date` from the query string. Calls
  `data.get_weekly_trend_data(lot_cds or None, include_recipes=False)` —
  **same underlying function as `recipe-statistics`, called with
  `include_recipes=False`** so the `*_rcp_info` keys are omitted from each
  bucket (this route only consumes `*_summary` data for its trend chart,
  and skipping `rcp_info` avoids serializing thousands of unused recipe
  rows). The route then filters the full date range down to
  `[start_date, end_date]` via lexicographic ISO-string comparison (dates
  are always `YYYY-MM-DD`, which sorts correctly as plain strings) and
  returns `{"dates": [...], "trend": {date: bucket, ...}}`.
- Contract: same `dict[str, TrendBucket]` as `recipe-statistics` above,
  except every bucket in practice only has the four `*_summary` keys
  populated (the `*_rcp_info` keys are `TypedDict`-optional via
  `total=False` specifically so both call shapes validate against the same
  `TrendBucket` contract).
- Mock behavior: same trend-generation logic as `recipe-statistics`
  (identical `_seed_for`-driven determinism, identical "don't change
  `points`" caveat), just with the recipe-detail lists stripped before
  return and a date-range slice applied by the route afterward instead of
  "take only the latest date."
- Office data source: **MinIO weekly snapshots** —
  `device_statistics/weekly_trend/YYYY-MM-DD.json`, summary-only, one object
  per week keyed by that week's Monday. The step index is a current-state
  index with no usable history, so past weeks cannot be reconstructed by
  query; a separate scheduler writes the snapshots via
  `write_weekly_snapshot()`. The current week has no snapshot yet and is
  computed live. A past week whose snapshot is missing is **omitted from the
  response** rather than emitted empty — an empty bucket would draw a
  0 on the trend chart and assert "nothing was measured that week". See
  `docs/datatables/device_statistics_weekly_trend.txt`.
- Notes: **huge-payload endpoint**, same class of concern as
  `recipe-statistics`/`recipe-params` — the original capture was 70 MB
  unfiltered. The parity harness pins `?lot_cds=R000` (~12 KB). Because
  this variant already omits recipe-level detail, its realistic per-request
  size (a handful of lots × 8 weekly points × 4 summary rows) is smaller
  than `recipe-statistics`'s even before any date-range narrowing is
  applied.

## mother_para 출처 — 해결됨 (office 확인 2026-08-10)

`mother_normal` 버킷은 파라미터마다의 mother 플래그를 필요로 합니다. 오랫동안
사무실에서 채울 방법이 없다고 보고 이 버킷을 비워 두었는데, 출처가 이미 있었습니다.

| 원천 | 상태 |
| --- | --- |
| `cdsem_idp_ver.raw_data` | **정본.** parameter 별 row 에 `Mother_Para` 가 있습니다 (office 확인 2026-08-10) |
| `cdsem_idp_ver.parameters` | `{name: point_count}` — 플래그를 담을 자리 없음. 여기만 보고 "출처 없음" 이라고 판단했던 것이 오진이었습니다 |
| 장비 FTP `{idp_name}.idp` | 같은 값의 원본. recipe 1건당 파일 1개라 이 화면 규모에서는 못 씁니다 |

FTP 경로를 못 쓰는 이유는 그대로입니다 — device 4000개 × recipe 100~200개.
recipe open 화면(`recipe_search`)이 그 경로를 쓰는 것은 사용자가 **한 recipe** 를
지목해 열기 때문입니다.

어댑터의 현재 동작 (`providers/office_example.py`):

1. `_IDP_SOURCE` 가 `raw_data` 를 **통째로가 아니라** `raw_data.Parameter` /
   `raw_data.Mother_Para` 두 경로로만 내려받습니다. 통째로 받으면 recipe 1건의
   parameter 표에 device 당 recipe 100~200 개가 곱해집니다.
2. `_raw_data_rows` 가 blob 을 row 목록으로 펴고 `_mother_names` 가 플래그를
   읽습니다. 확인된 형태는 row dict 의 list 이고, 나머지 분기(column 지향,
   이름-key, 세 table 을 감싼 형태)는 적재 표기가 바뀌었을 때를 위한 관용입니다.
3. `_flag` 는 **문자열을 추측하지 않습니다.** `bool("False")` 가 True 라서
   그냥 캐스팅하면 모든 parameter 가 mother 가 됩니다.
4. 읽을 수 없으면(`None`) 경고를 남기고, 읽혔는데 True 가 하나도 없으면 **다른**
   경고를 남깁니다. 두 상태는 화면상 똑같이 빈 버킷이지만 원인이 정반대입니다.

`only_normal` 로 슬쩍 대체하지 않는 것은 그대로입니다 — 그러면 요약은 숫자를
보여주는데 프론트엔드의 health 는 판정할 파라미터가 없어 0/0 이 되어, 한 표의
열들이 서로 다른 답을 하는 화면이 됩니다. 빈 버킷은 눈에 보이고, 이유는 로그가
말합니다.

**남은 확인** — `Mother_Para` 가 index 에도 진짜 bool 로 실려 있는지. 파서 쪽은
bool 이 확인되었지만(`docs/datatables/recipe_idp.txt`) 적재를 거치며 문자열이
되었을 수 있고, 그 경우 위 4번의 두 번째 경고가 뜹니다.

## Verify

    SKEWNONO_DEVICE_STATISTICS_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/device_statistics
