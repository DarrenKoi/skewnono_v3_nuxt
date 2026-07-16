# meas_hist — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
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
  set is fine. Rows are sorted by `timestamp` descending.
- Office data source: <!-- OFFICE: OpenSearch meas_hist index, bool filter on tool_type/fab_name/recipe_name -->
- Notes: `fab_name` is compared uppercased on both sides. `recipe_name`
  matches either the bare `recipe_name` or the `class/recipe` `full_name`.

## Endpoint: GET /api/meas-hist/search

- Handler: `routes.py` → `data.search_meas_hist(tool_type, fab, model, eq,
  recipe, lot, msr, q, date_from, date_to, offset, limit)`. `fab`/`model`/
  `eq`/`recipe`/`lot`/`msr`/`q` are repeated query params collected as lists
  (`?eq=A&eq=B`); `date_from`/`date_to` come from the `from`/`to` query
  params (`YYYY-MM-DD`); `offset` defaults to `0`, `limit` defaults to
  `DEFAULT_LIMIT` (50).
- Contract: `MeasHistSearchResponse` —

  ```python
  class MeasHistSearchResponse(TypedDict):
      total: int
      capped: bool
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
