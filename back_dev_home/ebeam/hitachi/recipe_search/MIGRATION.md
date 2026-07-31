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
| `/param-detail` | tool FTP raw folder → `office_utils.idp_amp_reader` | wired, unverified on real data |
| `/align-detail` | tool FTP raw folder → `office_utils.idp_amp_reader` | wired, unverified on real data |
| `/recipe-image` | tool FTP raw folder (bytes) | wired, unverified on real data |
| `/compare` | — | mock (re-exported) |

**The "compare is derived from open" invariant is knowingly broken office-side
right now.** `/recipe-detail` returns parsed IDP data while `/compare` returns
the mock's generator output for the same recipe, so the two disagree. Closing
that means one FTP session per distinct `eqp_ip` with every requested recipe's
`.idp` batched into a single `HostSpec(files=[...])` — compare accepts up to
200 names, and 200 sequential downloads would hold a worker for minutes.

`align_images` and `amp_info` used to be **fabricated even at the office**,
isolated in `_sourceless_extras()` against the day a source landed. It landed
on 2026-07-29: the raw-recipe folder beside the `.idp` (`data/{idw}/{idp}/`),
read by a second 사내 parser, `office_utils.idp_amp_reader`. Both keys and that
function are gone; three endpoints replace them.

### What the office adapter owes the raw-folder endpoints

- **`office_utils.idp_amp_reader`** must be importable — `read_amp_info`,
  `read_af_pr_condition`, `read_meas_image_condition`,
  `get_align_beam_pr_conditions`, `read_align_image_condition` — each accepting
  a path, bytes, or a string. A gitignored home stand-in of the same name exists
  at the repo root so the adapter can be written and run at home.
- **Align files take the last two readers, not the first three.** The ENAP
  settings go to `get_align_beam_pr_conditions`, which takes the whole align
  point list in **one** call; an align image's `cond.txt` goes to
  `read_align_image_condition(source, which)`, where `which` is `"OM"` for
  P.No 1 and `"SEM"` for P.No 2. Until 2026-07-29 `get_align_detail` used
  `read_af_pr_condition` and `read_meas_image_condition` here. Nothing failed —
  wrong parsers still return renderable values — so the swap was only visible in
  the values, at the office. `tests/test_align_readers.py` now asserts which
  reader receives what.
- **Naming is not the adapter's business.** Every path comes from
  `recipe_search/rawfiles.py`, which is pure and fully tested at home. Do not
  re-derive `.jpeg`, the `PR`→`EN` swap, the four-digit padding, or the
  `.`-prefixed `cond.txt` sidecar in the adapter. Schema of record:
  `docs/datatables/recipe_idp.txt`.
- **A missing file is not an error.** `_fetch_raw` logs it and omits it from the
  result; `_read_block` turns both an absent file and a reader that raises into
  `None`, which renders as 파일 없음 on a **200**. Only the FTP session itself
  failing may raise. A parameter legitimately lacking a third addressing image
  or an AF/PR setting is the common case.
- **`fetch_recipe_image` must raise `LookupError`** when the image is absent, so
  the route can answer 404 and `<img>` falls back to its own broken state rather
  than decoding a JSON error body as a picture.
- **`get_param_detail` groups by locator before fetching**, so a compare across
  N recipes on one tool is one FTP session rather than N.

### What the 2026-07-30 probe run changed

`scripts/probe_recipe_ftp.py` was run against real files and all five readers'
output is now recorded in `docs/datatables/recipe_idp.txt`. Three results
changed the adapter rather than only the documentation, so re-read them before
copying this template to `office.py`:

- **`get_align_beam_pr_conditions` keys its return by OPTIC** — `{"OM": …,
  "SEM": …}`. That answers the question this function was built to hedge: the
  single batched result **can** be split per align point, because P.No 1 is OM
  and P.No 2 is SEM. `_split_align_settings` now tries the optic branch first
  and keeps the older positional / name-keyed guesses behind it. A P.No outside
  1–2 is left out rather than handed an arbitrary optic's block.
- **`read_af_pr_condition` (ENMP) returns a dict OF DICTS** — eight groups. It
  is the only nested reader. `_to_rows` emits one row per inner key tagged with
  its group, and `SettingRow.section` (NotRequired) carries it to the screen;
  the four flat readers are untouched and render identically to before.
  **A row's identity is `(section, key)`, never `key`** — addressing pass 1 and
  pass 2 carry identical inner keys, and `Acceptance` appears in three ENMP
  groups plus ENAP. Anything joining on the bare key shows pass 1's value under
  both headings with no error and no blank cell.
- **Values are not all strings.** ENMP's `Wait(s)` and
  `Relative Position X/Y(um)` come back as Python floats beside `str` siblings
  in the same group, while the cond.txt readers and `read_amp_info` are
  genuinely all-`str`. `_to_rows` already stringifies every branch, so nothing
  broke — but do not add code that assumes a reader returned a string.

Field NAMES live in `docs/datatables/recipe_idp.txt` and are expected to change
as the office parser is refined. Nothing in the adapter keys off any of them;
that is what the open key/value `SettingBlock` buys. When they change, the
adapter needs no edit at all — only the mock's tables and that document.

### This screen is read-only

There is no write mode and no plan for one: it displays recipe settings.
`/compare` and `/param-detail` are POSTs only because they take a list body —
`/api/*` allows 20 requests per 5 s, and a 20-recipe compare would trip that as
separate GETs. The one local write in the adapter is a temp file, because
`combined_idp_info` takes a path rather than bytes. **Nothing may write to the
tool**: these are live metrology recipes on production equipment.

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
      idp_image_info: list[IdpImageInfoRow]
      locator: IdpLocator          # eqp_ip / class_name / idw / idp
      recipe_id: str
      fac_id: str
      tool_category: str
      timestamp: str
  ```

- Mock behavior: generates all five recipe-open tables for one recipe, seeded
  from `sha256(recipe_id:fac_id:tool_category)` (defaults `"DUMMY_RECIPE_001"`,
  `"R3"`, `"cd-sem"` when args are `None`) so a given recipe/fab/tool triple is
  reproducible. `wafer_mp_info` is 50 measurement-point rows, `wafer_align_info`
  is 10 alignment rows, and `idp_image_info` is 20 rows (one per synthetic
  parameter) whose five `img_*` values follow the office naming convention
  (`IMMP0001`, `PRMP0000`, `IMMS0000`, `PRMS0000`, `I2MP0000` — eight
  characters, no extension), with the French `"non"` sentinel on the optional
  slots so the no-file path is exercised at home. `locator` is derived from the
  recipe id, inside `10.0.0.0/8` so it survives `validate_tool_ip`; nothing
  listens on it, which is correct — no adapter opens a socket at home. AMP and
  the beam conditions are NOT part of this response: they are fetched per click
  through `/param-detail`
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
  `.item()`. Two cross-table invariants were confirmed at the same time:
  `Region == wafer_mp_info.P_No`, and `D_No == -1` ⟺
  `dnumber_removed == True`.
- **Those two invariants now hold in the home data (2026-07-31).** They had
  been written down and left unbuilt, so `providers/mock.py` and the
  `office_utils` stand-in drew `Parameter`, `P_No` and `dnumber_removed` from
  independent draws. At home the documented `Region` join therefore returned
  another parameter's rows, and `D_No` came from `randint(1, 100)` — so
  `D_No == -1`, the case the screen flags, occurred at **no** seed. Both
  generators now build a measurement point from one of `idp_image_info`'s
  parameters and take `P_No` and the `-1` from it; `tests/test_mock_cross_table.py`
  pins the relations without pinning any value. `Region` and `dnumber_removed`
  are parameter-level and so agree across a parameter's rows, while the `img_*`
  slots stay row-level and still differ — the distinction the param-detail cache
  bug of 2026-07-30 depended on. **The adapter still joins on `Parameter`**;
  moving it to the integer key is a separate change, now testable at home.
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
  tool_category=tool_type)` and reshapes its `idp_image_info` into
  a compact per-parameter view — so compare data always matches what
  `/recipe-detail` would return for the same recipe. `idp` is restricted to
  `COMPARE_IDP_FIELDS` (`Addressing`, `Double_Addressing`, `Mother_Para`,
  `Region`, `Meas_Counting`, `dnumber_removed`); `images` maps each
  `IMAGE_SLOTS` key to that parameter's slot value, which the client posts
  straight back as `/param-detail`'s `slots`. AMP is no longer part of this
  payload — compare fetches it per visible cell, so the two screens cannot
  disagree. Each recipe carries its own `locator`, because those fetches are per
  tool. Duplicate `Parameter` values within one
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

## 502 진단 (`/recipe-detail`)

`자세히 보기`가 502 를 반환할 때는 `.idp` 위치를 찾지 못한 것입니다. 위치 소스는
Redis 레지스트리와 meas_hist 두 개이므로 502 는 **둘 다 실패했다**는 뜻입니다.
브라우저에 보이는 문장은 meas_hist 만 지목하지만, 측정된 적 없는 recipe 에서
meas_hist 가 비어 있는 것은 정상이며 레지스트리가 바로 그런 recipe 를 위해
존재합니다. 따라서 실제로 물어야 할 것은 "레지스트리가 왜 답하지 않았는가"이고,
아래 스크립트가 두 소스의 각 단계를 순서대로 확인합니다.

    .venv/bin/python -m scripts.diagnose_recipe_search_office "1/AC_M2_TAT" --fab R3

읽는 법 — 502 본문에 `Redis recipe registry was tried first and declined: ...`
절이 있으면 배포된 `office.py` 가 레지스트리를 조회했고 그 이유를 말해 줍니다.
**그 절이 없으면** 배포본이 레지스트리 경로가 없던 시절의 STALE 사본이므로
Redis 를 아예 조회하지 않은 것입니다. 이때는 데이터가 아니라 사본을 고칩니다.

    python -m scripts.sync_office_adapters recipe_search
