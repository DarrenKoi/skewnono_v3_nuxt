# lateral_recipe — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/lateral

- Handler: `routes.py` → `data.get_lateral_recipe(tool_type, fab_name,
  recipe_name)`. `tool_slug` is `cdsem`/`hvsem`, resolved to `ToolType`
  (`"cd-sem"`/`"hv-sem"`) via `resolve_tool_type_from_slug` in
  `ebeam/hitachi/_tool_specs.py`; `fab_name` comes from the optional
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
  matches (case-insensitive), sorted by `eqp_id`. For each matching EQP, a
  deterministic RNG seeded from `sha256(tool_type:fab_name:recipe_name)`
  decides `recipe_ready` (`READY_RATIO = 0.65`) and, when ready, a
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
- Office data source: <!-- OFFICE: Redis hash `v3_tools_in_recipe_<fab>` keyed
  by recipe_name → list[eqp_id], joined with an OpenSearch table providing
  recipe_version per (eqp_id, recipe_name) -->
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

    SKEWNONO_LATERAL_RECIPE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/lateral_recipe
