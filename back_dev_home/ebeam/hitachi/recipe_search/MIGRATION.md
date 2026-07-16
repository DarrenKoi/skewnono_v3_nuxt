# recipe_search — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/recipes

- Handler: `routes.py` → `data.get_recipe_catalog(tool_type, fab_name)`.
  `tool_slug` is `cdsem`/`hvsem`, resolved to `ToolType` (`"cd-sem"`/`"hv-sem"`)
  via `TOOL_BY_SLUG`; `fab_name` comes from the `?fab_name=` query param
  (uppercased, `None` if blank).
- Contract: `RecipeSearchResponse` —

  ```python
  class RecipeSearchResponse(TypedDict):
      tool_type: ToolType
      fab_name: str | None
      total: int
      rows: list[RecipeSearchRow]  # RecipeSearchRow = str (a recipe name)
  ```

- Mock behavior: synthesizes exactly 50,000 recipe-name strings
  (`RECIPE_COUNT`), deterministically seeded from `sha256(tool_type:fab_name)`
  so repeated calls with the same `(tool_type, fab_name)` return byte-identical
  rows (`@lru_cache`-memoized in `_generate_recipe_rows`). Names follow the
  shape `"<CLASS>/<BASE>_ABC123_<VARIANT>_<00001-suffix>"`, cycling through 10
  fixed `(class, base)` patterns.
- Office data source: <!-- OFFICE: Redis-backed recipe-name list keyed by tool_type/fab_name -->
- Notes: per the module docstring, "the office source is expected to return
  only a large Redis-backed recipe-name list" — the office implementation is
  expected to be a plain name lookup, not the full synthetic generator.
  `total` must equal `len(rows)`.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/recipe-detail

- Handler: `routes.py` → `data.get_recipe_open_data(recipe_id=recipe_name,
  fac_id=fab_name, tool_category=tool_type)`. `recipe_name` is required
  (400 if missing/blank); `fab_name`/`tool_type` resolve the same way as
  `/recipes`.
- Contract: `RecipeDetailResponse` —

  ```python
  class RecipeDetailResponse(TypedDict):
      wafer_mp_info: list[WaferMpInfoRow]
      wafer_align_info: list[WaferAlignInfoRow]
      align_images: list[AlignImageRow]
      idp_image_info: list[IdpImageInfoRow]
      amp_info: list[AmpRow]
      recipe_id: str
      fac_id: str
      tool_category: str
      timestamp: str
  ```

- Mock behavior: generates all five recipe-open tables for one recipe, seeded
  from `sha256(recipe_id:fac_id:tool_category)` (defaults `"DUMMY_RECIPE_001"`,
  `"R3"`, `"cd-sem"` when args are `None`) so a given recipe/fab/tool triple is
  reproducible. `wafer_mp_info` is 50 measurement-point rows, `wafer_align_info`
  is 10 alignment rows, `align_images` is always exactly 2 rows (global + fine
  alignment), `idp_image_info` is 20 rows (one per synthetic parameter), and
  `amp_info` is `len(idp_image_info) * len(IMAGE_SLOTS)` rows — one AMP row
  per (parameter, image slot) pair, keyed off `IMAGE_SLOTS` (3 "address" slots
  + 2 "measure" slots). Address-role AMP rows populate
  `Template`/`MatchScore`/`SearchArea`/`Rotation` and null out
  `Algo`/`ROI`/`EdgeThr`/`EdgeDir`/`Smooth`; measure-role rows are the mirror
  image. `timestamp` is `datetime.now().isoformat()` — a volatile field
  scrubbed by the parity harness (`VOLATILE_KEYS`), so office does not need to
  match it byte-for-byte.
- Office data source: <!-- OFFICE: IDP payload fetch for the chosen recipe (wafer MP/align tables + image filenames + AMP) -->
- Notes: this endpoint mimics "the IDP payload the frontend will request
  after a user chooses one recipe" (module docstring) — unlike `/recipes`,
  the office implementation is expected to assemble real per-recipe detail
  data, not a name-only lookup.

## Endpoint: POST /api/\<tool_slug\>/recipe-search/compare

- Handler: `routes.py` → `data.get_recipe_compare_data(tool_type, fab_name,
  recipe_names)`. The request body comes from the frontend compare picker
  (see `front-dev-home` recipe-search compare UI) as JSON:
  `{"recipe_names": [...], "fab_name": "..."}`. `recipe_names` must be a
  non-empty list (400 if missing/empty/not-a-list) capped at 200 entries
  (400 if exceeded); `fab_name` is optional, uppercased, `None` if blank.
- Contract: `RecipeCompareResponse` —

  ```python
  class RecipeCompareResponse(TypedDict):
      tool_type: ToolType
      fab_name: str | None
      recipes: list[CompareRecipe]

  class CompareRecipe(TypedDict):
      recipe_id: str
      fac_id: str
      parameters: list[CompareParameter]

  class CompareParameter(TypedDict):
      Parameter: str
      idp: dict[str, object]    # subset of IdpImageInfoRow: COMPARE_IDP_FIELDS
      images: dict[str, str]    # IMAGE_SLOTS key -> filename
      amp: list[AmpRow]
  ```

- Mock behavior: for each name in `recipe_names` (blank names skipped after
  `.strip()`), calls `get_recipe_open_data(recipe_id=name, fac_id=fab_name,
  tool_category=tool_type)` and reshapes its `idp_image_info`/`amp_info` into
  a compact per-parameter view — so compare data always matches what
  `/recipe-detail` would return for the same recipe. `idp` is restricted to
  `COMPARE_IDP_FIELDS` (`Addressing`, `Double_Addressing`, `Mother_Para`,
  `Region`, `Meas_Counting`, `dnumber_removed`); `images` maps each
  `IMAGE_SLOTS` key to that parameter's filename; `amp` is that parameter's
  AMP rows grouped by `Parameter`. Duplicate `Parameter` values within one
  recipe's `idp_image_info` are de-duplicated (first occurrence wins).
- Office data source: <!-- OFFICE: same IDP payload source as /recipe-detail, batched per recipe_names -->
- Notes: `get_recipe_compare_data` reuses `get_recipe_open_data` internally
  "so compare matches open" (source comment) — an office implementation
  should preserve that invariant (compare output for a recipe should be
  derivable from / consistent with that recipe's `/recipe-detail` output)
  rather than hitting a separate data path that could drift.

## Verify

    SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
