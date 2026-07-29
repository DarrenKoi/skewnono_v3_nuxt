# recipe_search — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`, or
  `contracts.py`.
- Never change `providers/mock.py` **behavior** or its generated values — its
  docstring is maintained under the "office DB knowledge lands in TWO places"
  rule (root `CLAUDE.md`), alongside `docs/datatables/*.txt`, so the docstring
  itself may still change.
- `tests/` is off-limits to whoever is implementing `providers/office.py` at
  the office. It is not off-limits to the template author adding
  home-runnable gates for logic that ships in `office_example.py` — those
  additions are how this branch's `test_idp_locate.py` came to exist.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Status: partially wired

| Endpoint | Office source | State |
| --- | --- | --- |
| `/recipes` | Redis hash per tool family | wired |
| `/recipe-detail` | Redis recipe registry (fallback: meas_hist) → tool FTP `.idp` → `office_utils.read_idp_info` | wired, unverified on real data |
| `/compare` | — | mock (re-exported) |

**The "compare is derived from open" invariant is knowingly broken office-side
right now.** `/recipe-detail` returns parsed IDP data while `/compare` returns
the mock's generator output for the same recipe, so the two disagree. Closing
that means one FTP session per distinct `eqp_ip` with every requested recipe's
`.idp` batched into a single `HostSpec(files=[...])` — compare accepts up to
200 names, and 200 sequential downloads would hold a worker for minutes.

Two fields stay **fabricated even at the office** because the parser does not
return them: `align_images` and `amp_info`. They are isolated in
`_sourceless_extras()` so there is one place to delete when a source lands; the
candidate is the raw-recipe folder beside the `.idp` (`data/{idw}/{idp}/`).

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
- Office data source: **WIRED — tool FTP, located from the Redis recipe
  registry or, failing that, from measurement history.** Five steps, one
  function each, because only the first three need the office:

  | Step | Function | Source | Runs at home? |
  | --- | --- | --- | --- |
  | locate (1st) | `_locate_via_redis` | `v3_*_rcp_loc_*` + `v3_*_tools_in_rcp_*` + sem_list | no |
  | locate (2nd) | `_locate_via_meas_hist` | `meas_hist_{cdsem,hvsem}` | no |
  | fetch | `_download_first` → `_download_idp` | tool FTP (`SKEWNONO_TOOL_FTP_*`) | no |
  | parse | `_parse_idp` | `office_utils.read_idp_info` | via stand-in |
  | map | `_to_detail_response` | pure | yes |

  `recipe_id` is the catalog's `"class/recipe"` string, which is both the
  registry hash field and meas_hist's `full_name` — so the id the search table
  hands back is already the lookup key, and its `/` prefix is the FTP class
  directory. The Redis registry is tried first and is all-or-nothing: if either
  hash misses, or `fac_id` is blank, the whole location falls to meas_hist rather
  than blending the two. Both paths return tool candidates in preference order
  (registry: `available == "On"` first; meas_hist: newest run first) and
  `_download_first` walks them until one serves the file. On the meas_hist
  path, up to `_LOCATE_CANDIDATES` documents are fetched (newest first) and
  any one missing an `eqp_ip`, `class_name`, `idw_name`, or `idp_name` is
  skipped in favor of the next rather than failing the request.
  - Recipe in neither the registry nor meas_hist → `LookupError` (502).
  - Every candidate tool refused or lacked the file → `LookupError` (502)
    naming each tool tried and why.
  - `eqp_ip` outside `SKEWNONO_TOOL_SUBNETS` → that candidate is skipped with a
    WARNING; if **every** candidate is outside, `InvalidToolIp` is raised. The
    IP comes from Redis or OpenSearch rather than a client, but the backend
    still opens a socket to it, so the SSRF guard applies. **Status: generic
    JSON 500, not 502.** `InvalidToolIp` descends from `MsrImageError`
    (`back_dev_home/msr_image/errors.py`), and `back_dev_home/__init__.py`
    registers error handlers for `HTTPException`, the exact `LookupError` and
    `RuntimeError` types, and the redis/opensearch driver errors — but none
    for `MsrImageError`. So this case falls through to Flask's own
    `InternalServerError` wrapping, which the app's `HTTPException` handler
    turns into a generic message. The blocked IP lands only in the server
    log (Flask logs the original exception before wrapping it); unlike the
    sibling failures above, the JSON response body carries no per-tool
    detail.
  - `office_utils` not importable → `RuntimeError` (503, unconfigured).
  - Parser returns the wrong keys → `LookupError` (502).
  - A documented column the parser stopped emitting is **nulled, not dropped**
    (WARNING logged); an undocumented one it started emitting is **dropped**
    (INFO logged). Neither changes the response shape.
- **`idp_image_info` dtypes corrected 2026-07-28** (office 확인, first real
  `combined_idp_info()` output). `Addressing`, `Mother_Para` and
  `dnumber_removed` are `bool`; they had been documented and mocked as a
  `"Yes"`/`"No"` string, a parent parameter *name*, and an int64 count
  respectively. `Mother_Para == True` means the row's own parameter is a
  mother (usually `SEQ == 1`) whose image its sons measure from — it never
  carried another parameter's name. `dnumber_removed == True` means the
  parameter's data is suppressed and reaches no legacy system. The adapter
  needed **no logic change**: `_scalar` already converts `numpy.bool_` via
  `.item()`. Two cross-table invariants were confirmed at the same time and
  are recorded but **not yet acted on**: `Region == wafer_mp_info.P_No`, and
  `D_No == -1` ⟺ `dnumber_removed == True`.
- **Writing this adapter at home:** `office_utils` exists only on office
  machines, so a stand-in package of the same name lives at the repo root and
  is **gitignored** (`/office_utils/`) — never commit it, or it shadows the
  real parser at the office and serves fabricated data at HTTP 200. It matches
  the signature, the three keys, and the column names/order/dtypes, so
  everything below the parse is runnable here. `tests/test_idp_mapping.py`
  covers the mapping with hand-built DataFrames and needs neither
  `office_utils` nor `office.py`, so it also runs on a clean checkout.
  Details: `docs/datatables/recipe_idp.txt` §집에서의 대역.
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
- Office data source: **NOT WIRED — mock-backed**, and now the only endpoint
  that is. Re-exported (not reimplemented) so that when the batched IDP fetch
  lands it can be derived from open rather than growing a second data path.
  Until then compare disagrees with `/recipe-detail` for the same recipe;
  see Status above.
  <!-- OFFICE: same IDP payload source as /recipe-detail, batched per recipe_names -->
- Notes: `get_recipe_compare_data` reuses `get_recipe_open_data` internally
  "so compare matches open" (source comment) — an office implementation
  should preserve that invariant (compare output for a recipe should be
  derivable from / consistent with that recipe's `/recipe-detail` output)
  rather than hitting a separate data path that could drift.

## Verify

    SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
