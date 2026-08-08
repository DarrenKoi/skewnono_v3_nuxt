# meas_hist — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- `fail_ratio` is a PERCENTAGE, 0..100 (`4.57` = 4.57%). It is computed at
  ingestion and stored on the document, so read the field — do not re-derive
  it from `fail_images` / `total_images`, and do not rescale it. Nothing
  downstream multiplies by 100; the UI appends `%` to the number as it stands.
- Unlike recipe_tat/fail_issue, this feature did NOT gain a `fab_names`
  tuple in the multi-fab selection work: `/meas-hist`'s `fab_name` stays a
  single `str | None`, and `/meas-hist/search`'s `fab` stays the
  already-plural `list[str] | None` it was before that work (an OR filter,
  unrelated to the sidebar's multi-fab selection). The frontend narrows the
  sidebar's selection down to `useFabRoute().primaryFab` before calling
  `/api/meas-hist` — intentional for Phase 1, revisit only if Phase B widens
  this endpoint too.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/meas-hist

- Handler: `routes.py` → `data.get_meas_hist(tool_type, fab_name, recipe_name)`,
  where `tool_type` is resolved from the `tool_type` query param (must be
  `"cd-sem"` or `"hv-sem"`, otherwise `None`), `fab_name` is uppercased, and
  `recipe_name` is passed through as-is.
- Contract: `MeasHistResponse` —

  ```python
  class MeasHistResponse(TypedDict):
      tool_type: ToolType | None
      fab_name: str | None
      recipe_name: str | None
      total: int
      rows: list[MeasHistRow]
  ```

- Mock behavior: filters the full in-memory row set by `tool_type` /
  `fab_name` (case-insensitive) / `recipe_name` (matches `full_name` OR
  `recipe_name` exactly). If a `recipe_name` filter is supplied and matches no
  existing rows, the mock synthesizes a small batch of plausible rows for
  that recipe (`_synthesize_for_recipe`) rather than returning an empty list —
  an office adapter should NOT reproduce synthesis; a genuinely empty result
  set is fine. Rows are sorted by `timestamp` descending. Results are limited
  to the last `RECIPE_HISTORY_DAYS` (30) — see the note below.
- Office data source: **WIRED.** OpenSearch `meas_hist_{cdsem,hvsem}`, bool
  filter: a `timestamp` range for the 30-day window, `fab_name.keyword` term,
  and an exact `should` on `full_name.keyword` / `recipe_name.keyword`.
- Notes: `fab_name` is compared uppercased on both sides. `recipe_name`
  matches either the bare `recipe_name` or the `class/recipe` `full_name`,
  exactly — via the `.keyword` sub-fields office-side, because the base
  mappings are analyzed `text` and would match on shared tokens.
- **Default window:** this endpoint returns only the last
  `RECIPE_HISTORY_DAYS` (30) days, narrower than the 60-day retention that
  still governs `/meas-hist/search` (where the user has explicit date
  controls). The constant lives in `providers/mock.py` and is imported by the
  office adapter, so the two phases cannot disagree about how much history
  "default" means. Office-side the window is anchored on `get_anchor_time()`
  (latest ingested data), not wall-clock, so an ingestion pause does not
  silently empty the view; it is a filter clause, so it bounds `total` too.
  There is no per-request override yet — adding one means a `days` query
  param through `routes.py` → `data.py` → both providers.

## Endpoint: GET /api/meas-hist/search

- Handler: `routes.py` → `data.search_meas_hist(tool_type, fab, model, eq,
  recipe, lot, msr, q, date_from, date_to, offset, limit)`. `fab`/`model`/
  `eq`/`recipe`/`lot`/`msr`/`q` are repeated query params collected as lists
  (`?eq=A&eq=B`); `date_from`/`date_to` come from the `from`/`to` query
  params (`YYYY-MM-DD`); `offset` defaults to `0`, `limit` defaults to
  `DEFAULT_LIMIT` (50).
- Contract: `MeasHistSearchResponse` —

  ```python
  class MeasHistRecipeName(TypedDict):
      full_name: str
      fab_name: str   # "" = owner unknown (fab_name 없는 문서)

  class MeasHistSearchResponse(TypedDict):
      total: int
      capped: bool
      recipe_names: list[MeasHistRecipeName]
      recipe_names_complete: bool
      offset: int
      limit: int
      range: dict[str, str]   # {from, to, anchor} — all YYYY-MM-DD
      out_of_retention: bool
      rows: list[MeasHistRow]
  ```

- Mock behavior: the caller's `date_from`/`date_to` range is intersected with
  a fixed `RETENTION_DAYS` (60-day) window anchored at `RETENTION_ANCHOR`. A
  present-but-unparseable date, or a range that falls entirely outside
  retention, sets `out_of_retention: True` and returns zero rows (it does
  NOT silently widen to the full window). Within a field, list values OR
  together (e.g. multiple `eq` values); across fields, filters AND together.
  `recipe`/`q` are substring/OR-fallback text matches, not exact. Results are
  sorted by `timestamp` descending, truncated to `MAX_RESULT_WINDOW` (10000)
  before pagination (`capped: True` if `total` exceeds that ceiling), then
  paginated by `offset`/`limit` (`limit` clamped to `[1, DEFAULT_LIMIT * 10]`).
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, bool{must:[terms...]} + date range query -->
- **레시피 이름 스냅샷:** 유효한 구조화 `recipe` 검색어가 있는 요청만
  `recipe_names` 열거를 수행합니다. 2026-08-08부터 스냅샷 항목은 문자열이
  아니라 `{full_name, fab_name}` 쌍입니다 — recipe-search fallback이 발견한
  이름에 FAB 배지·소유 FAB 라우팅을 붙이기 위해서입니다. Mock provider는
  모든 필터를 적용한 전체 후보에서 raw row 페이지를 자르기 전에 중복 없는
  `(full_name, fab_name)` 쌍을 계산합니다. Office provider는 raw search와
  동일한 bool query로 `full_name.keyword` composite aggregation을 돌리되,
  버킷마다 `fabs` terms sub-aggregation(`fab_name.keyword`, size 16)을
  붙여 쌍을 얻습니다. `fabs` sub-aggregation 자체가 없는 응답은 어댑터
  버그로 보고 RuntimeError를 던지지만, fab 버킷이 비어 있는 이름(문서에
  `fab_name`이 없는 dirty data)은 `fab_name: ""`으로 살려 둡니다 — 이름을
  숨기는 쪽이 더 나쁘기 때문입니다. 열거가 정상 완료된 보존 기간 내 요청은
  raw row의 `offset`/`limit` 및 `MAX_RESULT_WINDOW`와 관계없이
  `recipe_names_complete: true`를 반환합니다. **이 계약 변경으로 사무실에서
  `office.py` 재복사가 필요합니다** — 구형 복사본이 문자열 스냅샷을
  반환하면 프론트엔드는 배지 없는(owner unknown) 행으로 강등해 동작은
  유지되지만, 부팅 로그의 `STALE office.py` 표시가 재복사를 안내합니다.
- 구조화 `recipe` 검색어가 없으면 열거를 요청하지 않으므로
  `recipe_names: []`, `recipe_names_complete: false`를 반환합니다. 날짜가
  잘못되었거나 요청 범위가 보존 기간보다 완전히 과거 또는 미래이면
  `out_of_retention: true`, `recipe_names: []`,
  `recipe_names_complete: false`를 반환하며 OpenSearch 검색과 이름 열거를
  수행하지 않습니다. 소비자는 `recipe_names_complete: false`를 완전한
  빈 결과로 해석하면 안 됩니다.
- **카테고리 / tool_type:** the skewvoir 검색 UI sends `tool_type` only when
  the user picks exactly one 카테고리 (CD-SEM → `cd-sem`, HV-SEM →
  `hv-sem`). No pick (or both picked) omits the param, and the office
  adapter must then search BOTH aliases in one request
  (`meas_hist_cdsem,meas_hist_hvsem` — `ALL_INDICES` in
  `_office_meas_hist.py`), deriving each row's `tool_type` from its
  `_index` name. The FAB → 카테고리 → 장비 모델 → EQ dropdown cascade is
  frontend-only (joined through `sem_list`), so it needs no office work
  here.
- Notes: `range.to` in the response is the caller-facing INCLUSIVE end date
  (clamped to the retention ceiling), distinct from the internal filtering
  bound which is shifted one day forward to make the day-granular comparison
  inclusive — office adapters should report the same caller-facing semantics.
  `msr` values are compared case-sensitively (exact set membership); every
  other list filter is uppercased on both sides.

## Endpoint: GET /api/meas-hist/facets

- Handler: `routes.py` → `data.get_meas_hist_facets(tool_type)`.
- Contract: `MeasHistFacetsResponse` —

  ```python
  class MeasHistFacetsResponse(TypedDict):
      tool_type: ToolType | None
      anchor: str
      retention_days: int
      fab: list[MeasHistFacetValue]     # {value: str, count: int}
      model: list[MeasHistFacetValue]
      eq: list[MeasHistFacetValue]
  ```

- Mock behavior: aggregates `fab_name` / `eqp_model_cd` / `eqp_id` counts
  over rows within the retention window (optionally filtered by
  `tool_type`), sorted alphabetically by value. `recipe` is deliberately NOT
  aggregated here (hundreds of distinct recipes in the office index) — recipe
  discovery goes through the search bar's free-text `recipe` param instead.
- Office data source: <!-- OFFICE: OpenSearch terms aggregation over the same bool filter used by /search -->
- Notes: `anchor`/`retention_days` describe the window the facet counts were
  computed over and should be echoed from the same retention configuration
  used by `/search`.

## Read path: find_meas_hist_by_msr(msr)

- Called internally (스큐보아 / 스큐노노 MSR detail flow) to look up the parent
  measurement-history row for a given `msr` before opening its raw detail
  (`msr_file`). Not exposed as its own HTTP route.
- Contract: `MeasHistRow | None` — see the shared `MeasHistRow` TypedDict in
  `contracts.py`.
- Mock behavior: indexed lookup (`msr -> MeasHistRow`) over the pre-built row
  set only; recipe-search-synthesized rows are not indexed, since callers
  select from real rows before requesting detail. Returns `None` for an
  unknown `msr` rather than raising.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, exact-match lookup by msr -->
- Notes: must return `None` (not raise, not an empty dict) for an unknown
  `msr` so downstream 404 handling keeps working unmodified.

## Verify

    SKEWNONO_MEAS_HIST_PROVIDER=office .venv/bin/pytest back_dev_home/meas_hist
