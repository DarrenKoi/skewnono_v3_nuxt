# lateral_recipe — office migration

## Rules

- Edit the tracked `providers/office_example.py`, then keep the ignored
  office-local `providers/office.py` copy in sync. Do not change `routes.py`,
  `data.py`, `providers/mock.py`, or `contracts.py` for office wiring.
- Keep pure office-adapter regression tests runnable at home; keep live
  OpenSearch/Redis checks in a separate, environment-gated local test.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/lateral

- Handler: `routes.py` → `data.get_lateral_recipe(tool_type, fab_name,
  recipe_name)`. `tool_slug` is `cdsem`/`hvsem`, resolved to `ToolType`
  (`"cd-sem"`/`"hv-sem"`) via `resolve_sem_tool_type` in
  `ebeam/_slug_routes.py` — it accepts only `SEM_TOOL_SLUGS`, so an AMAT slug
  is a `400` rather than a fabricated fleet; `fab_name` comes from the optional
  `?fab_name=` query param (uppercased, `None` if blank); `recipe_name` comes
  from the `?recipe_name=` query param and is **required** (400 if
  missing/blank — `routes.py` returns
  `{"error": "recipe_name is required"}` before calling `data.py`).
- Contract: `LateralRecipeResponse` —

  ```python
  class LateralRecipeResponse(TypedDict):
      tool_type: ToolType
      fab_name: str | None
      recipe_name: str
      total_tools_in_fab: int
      ready_count: int
      not_ready_count: int
      latest_recipe_version: int | None
      latest_generated_at: str | None
      versions: list[LateralRecipeVersion]
      rows: list[LateralRecipeRow]

  class LateralRecipeVersion(TypedDict):
      recipe_version: int
      generated_at: str
      ready_count: int

  class LateralRecipeRow(TypedDict):
      eqp_id: str
      eqp_model_cd: str
      vendor_nm: Literal["HITACHI", "AMAT"]
      available: Literal["On", "Off"]
      recipe_ready: bool
      recipe_version: int | None
      recipe_generated_at: str | None
  ```

- Mock behavior: the tool population comes from `sem_list.data.get_sem_list()`
  filtered to rows whose `eqp_model_cd` maps to the requested `tool_type`
  (via `model_to_tool_type`) and, if `fab_name` is given, whose `fab_name`
  matches (case-insensitive), sorted by `eqp_id`. Readiness has a hard floor:
  every EQP that `meas_hist.providers.mock.get_meas_hist(tool_type, fab_name,
  recipe_name)` reports a row for is `recipe_ready=True`, because a tool cannot
  have 측정 이력 for a recipe it does not hold. The remaining tools fall to a
  deterministic RNG seeded from `sha256(tool_type:fab_name:recipe_name)`
  (`UNMEASURED_READY_RATIO = 0.35`, low because the measured floor already
  carries most of the readiness — a flat 0.65 on top of it emptied the 미보유
  tab on nearly half the fab/recipe pairs). Both RNG draws (readiness,
  version) are consumed for every tool regardless of the measurement set, so
  the set decides only *who* is ready and never reshuffles its neighbours'
  versions. A ready tool gets a
  `recipe_version` in `RECIPE_VERSION_RANGE = (1, 7)`. Each `(tool_type,
  fab_name, recipe_name, version)` combination maps to a fixed
  `recipe_generated_at` derived from a base timestamp
  (`RECIPE_GENERATED_AT_BASE = 2026-05-20T09:00:00Z`) minus
  `(RECIPE_VERSION_RANGE[1] - version) * 5` days and a seeded jitter of up to
  12 hours — fully deterministic, no `datetime.now()` in the response path, so
  repeated calls with identical arguments are byte-identical. `versions` is
  the distinct `(recipe_version, generated_at, ready_count)` triples across
  all rows, sorted by version descending; `latest_recipe_version` /
  `latest_generated_at` come from `versions[0]` (or `None` if no rows are
  ready). `total_tools_in_fab` is `len(rows)`; `ready_count` /
  `not_ready_count` partition that total.
- Office data source: **WIRED.** OpenSearch aliases `cdsem_idp_ver` /
  `hvsem_idp_ver`, one document per **(recipe, version)**. Searching a
  `full_name` returns the recipe's whole version history; the highest
  `version` is the current one.
  - Exact recipe match goes through `full_name.keyword`, and the fab filter
    through `fab_name.keyword` (uppercase). The base mappings are `text`, so
    a `term` on them matches nothing and a `match` matches on shared tokens
    — `"1/AC_M2_TAT"` analyzes to `[1, ac, m2, tat]`.
  - `eqp_id` (보유) / `not_found_eqp_id` (미보유) are arrays. A tool's row
    version is the **highest** version doc listing it, i.e. what it runs now.
  - Recent measurement history is a readiness floor. The adapter walks
    distinct `eqp_id.keyword` buckets for the exact `full_name.keyword` and
    `fab_name.keyword` in the same 30-day window used by 측정 이력. A measured
    roster tool missing from every IDP `eqp_id` array receives the newest
    discovered version; an explicit IDP version assignment always wins.
    Equipment IDs are joined case-insensitively.
  - `recipe_generated_at` ← `modified`, emitted with an explicit `+09:00`.
    The office indices store KST wall-clock without an offset and the
    frontend formats via `new Date(iso).getHours()` (local time), so a `Z`
    suffix would tag 12:00 KST as 12:00 UTC and render it as 21:00 — 9 hours
    late. **Verify on the first office run** that `modified` really does
    arrive offset-less; if ingestion writes a `Z`-suffixed KST wall-clock,
    `_kst_iso` converts it and lands 9 hours off in the other direction.
  - `versions` lists **every** version doc, including ones no tool currently
    holds, so the revision history stays browsable; the frontend dims
    zero-holder cards. `ready_count` is counted from the assembled rows, not
    from the documents' `no_of_eqp_id`, so a card's number always equals
    what is countable in the table below it.
  - `_source` is trimmed to the three fields read (`version`, `modified`,
    `eqp_id`). `parameters` and `raw_data` are object blobs this endpoint
    never touches. `not_found_eqp_id` is not fetched because it cannot
    override recent evidence that a tool executed the recipe.
  - More than `MAX_VERSION_DOCS` (200) version docs raises rather than
    silently truncating — a partial history would misreport which tools are
    current.
- Not yet used from the index: `parameters`, `para_loc`, `minio_path`,
  `class_name`, `creator`, `created_tool`, `no_of_meas_point`. These are for
  the planned version-card detail view (click a version → `modified` plus
  `parameters` as a table), which needs a contract extension —
  `LateralRecipeVersion` has nowhere to put them today.
- Cross-feature note: the mock derives the EQP population from
  `sem_list.data.get_sem_list()` so the table always lists the same
  `eqp_id`s as the tool inventory view for the same
  tool/fab. An office implementation should preserve that invariant — the
  `rows` returned here should agree with whatever office source backs
  `sem_list` for the equipment identity fields (`eqp_id`, `eqp_model_cd`,
  `vendor_nm`, `available`), even though `recipe_ready`/`recipe_version`/
  `recipe_generated_at` come from the separate lateral-recipe source
  described above.

## Verify

    SKEWNONO_LATERAL_RECIPE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/lateral_recipe
