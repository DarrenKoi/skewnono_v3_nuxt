# recipe_search — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Status: partially wired

`/recipes` reads the office Redis catalog. `/recipe-detail` and `/compare`
still return mock IDP data, because the raw recipe-open data is not prepared
office-side yet — `providers/office.py` re-exports those two straight from
`providers/mock.py`.

That is a net improvement over leaving the whole feature on `mock` (the
catalog becomes real, detail is synthetic either way), which is why
`providers/office.py` is copied for `recipe_search` at all. The caveat worth
remembering: **at the office, 열어보기 shows plausible-looking synthetic
tables.** Anyone comparing them against the tool will find they do not match.

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
- Office data source: **WIRED.** Redis hash per tool family —
  `v3_cdsem_unique_rcp_list` (cd-sem) / `v3_hvsem_unique_rcp_list` (hv-sem).
  Fields are **lowercase** fab names, values are that fab's recipe-name list
  (`{"m14a": ["1/AC_M2_TAT", ...], "r3": [...]}`). `routes.py` uppercases
  `fab_name`, so the adapter lowercases at the Redis boundary and echoes the
  caller's uppercase spelling back in the response.
  - Missing hash *field* (unknown fab) → empty `rows`, `total: 0`.
  - Missing hash *key* → `LookupError` (JSON 502): the upstream job never ran.
  - No `fab_name` → union of every field, de-duped. The frontend always sends
    a fab, so this is the blank-query edge case only.
  - Values parse as JSON, then Python `repr`, then comma-separated, so the
    adapter does not care which the writer job used.
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
- Office data source: **NOT WIRED — deliberately mock-backed.** `providers/office.py`
  re-exports the mock's `get_recipe_open_data`. This keeps 열어보기 clickable
  and the contract gate green, at the cost of showing synthetic detail data
  in the office UI. The source itself is no longer unknown, though: the IDP
  file sits on the measuring tool's FTP server and `office_utils.read_idp_info`
  parses it into three DataFrames — chain, paths and full column contract in
  `docs/datatables/recipe_idp.txt`.
  <!-- OFFICE: IDP payload fetch for the chosen recipe (wafer MP/align tables + image filenames + AMP) -->
- **Writing this adapter at home:** `office_utils` exists only on office
  machines, so a stand-in package of the same name lives at the repo root and
  is **gitignored** (`/office_utils/`) — never commit it, or it shadows the
  real parser at the office and serves fabricated data at HTTP 200. It matches
  the signature, the three keys, and the column names/order/dtypes, so the
  DataFrame → `RecipeDetailResponse` mapping is fully runnable here; only the
  OpenSearch lookup and the FTP fetch are unreachable from home. Keep those two
  and the pure mapping in separate functions so the mapping stays testable
  without either. Details: `docs/datatables/recipe_idp.txt` §집에서의 대역.
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
- Office data source: **NOT WIRED — deliberately mock-backed**, same reason
  as `/recipe-detail`. Re-exported (not reimplemented) from the mock so the
  "compare is derived from open" invariant below survives the swap.
  <!-- OFFICE: same IDP payload source as /recipe-detail, batched per recipe_names -->
- Notes: `get_recipe_compare_data` reuses `get_recipe_open_data` internally
  "so compare matches open" (source comment) — an office implementation
  should preserve that invariant (compare output for a recipe should be
  derivable from / consistent with that recipe's `/recipe-detail` output)
  rather than hitting a separate data path that could drift.

## Verify

    SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
