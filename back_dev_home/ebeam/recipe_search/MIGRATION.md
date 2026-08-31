# recipe_search — office migration

## ⚠ Required before the first office deploy after 2026-08-09

This feature's office adapter drives the same vendored `ftp_handler` proxy
transport as `msr_image`, and shares its FTP account configuration
(`msr_image.config.load_config`). Since 2026-08-28 the client sends the account
per spec — `SKEWNONO_TOOL_FTP_ACCOUNTS` for the fab/tool exceptions, otherwise
`SKEWNONO_TOOL_FTP_USER` — so the proxy host's `FTP_PROXY_FTP_USER` /
`FTP_PROXY_FTP_PASSWORD` are only a fallback and no longer required.

**`office.py` 를 다시 복사하십시오** — `cp providers/office_example.py
providers/office.py`. 2026-08-28 변경이 `office_example.py` 의 spec 생성부를
고쳤으므로, 복사하지 않은 사본은 계정을 싣지 않은 채로 계속 동작합니다. 오류가
아니라 **틀린 계정으로 접속**하는 형태라 로그만 봐서는 드러나지 않습니다.
(Between 2026-08-09 and 2026-08-28 the proxy ignored
`config.ftp_user` entirely and reached every tool as the environment account.)
Full context:
[`back_dev_home/msr_image/MIGRATION.md`](../../msr_image/MIGRATION.md); the
proxy host's own deploy procedure is
[`docs/deployment-ftp-proxy.md`](../../../docs/deployment-ftp-proxy.md).

Those two are the **fleet default**, not the only account available. Since
2026-08-10 a `HostSpec` may carry its own `user`/`password` covering one host,
which is how a fleet spanning two vendors' tools gets two logins. Every tool
this adapter reaches today shares the Hitachi account, so nothing here passes
them yet — wire them in when a non-Hitachi family arrives, not before.

Also worth knowing: this adapter builds **one spec per host** — every file for
a tool rides a single connection — and does not set `host_timeout`, so it keeps
the library default (60s direct / 45s proxy) no matter how many raw files a
request asks for. That is a clean failure rather than corruption, because
`download()` runs in collect mode with no `on_file` writing into caller state,
but a large raw-folder fetch can hit it. `msr_image` scales its budget by
files-per-connection; do the same here if a real request is seen timing out.

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
| `/align-images` | Redis recipe registry (fallback: meas_hist) → tool FTP raw-folder listing | wired, unverified on real data |
| `/recipe-image` | tool FTP raw folder (bytes), MinIO write-through cache | wired, unverified on real data |
| `/compare` | — | mock (re-exported) |
| `/registry-check` | Redis recipe registry (2 `hget` per recipe) | wired, unverified on real data |

### `/align-images` — the caller names the tool

Built for the live-alarm board's ALIGNMENT FAIL rows. It differs from every
other endpoint here in one way that matters office-side: the caller passes an
`eqp_id`, and that becomes `prefer` on `_locate_idp`, so the requested tool is
tried first **even when the roster reports it `available="Off"`**.

That is not a nicety. `_order_candidates` sorts available tools first, so
without the preference an offline alarming tool sorts behind its siblings and
the walk returns a DIFFERENT tool's copy of the recipe. Tools hold different
versions of the same recipe — that divergence is the entire reason
`lateral_recipe` exists — so the engineer would be judging "is this align
target weak" against a file that is not the one that failed. The response
carries `eqp_id` (who answered) alongside `requested_eqp_id`, and the screen
shows a warning when they differ, so a substitution is never silent.

One NLST round trip happens here, and it is load-bearing (2026-08-22). This
endpoint used to compute the names instead — `align_reference_images()` returned
`ALIGN_OPTICS` verbatim, so the answer was always `IMAP0001.jpeg` and
`IMAP0002.jpeg`. A recipe that aligns on the OM alone has no `IMAP0002.jpeg`,
and publishing that name made `/recipe-image` answer 404 every time the screen
opened, which is what production reported. Every other read path here drops a
missing file and answers 200; `/recipe-image` is one GET per file and has
nowhere to drop it to, so **an endpoint that hands the browser a file name owns
checking that the file exists.**

`_list_raw_dirs` therefore runs before the response is built, and a listing it
cannot perform is `SourceUnavailable` (503) rather than an empty image set:
"the tool did not answer" and "this recipe has no align images" are different
answers on an ALIGNMENT FAIL screen. The cost is one round trip on a host the
image fetches were about to dial anyway; on a tool that is down the wall clock
is unchanged, because the two `<img>` requests previously spent the same
connect timeout in parallel.

### `/recipe-image` now caches

The route was "FTP to memory to response" — every viewer paid a full visit to
the tool. Two guards were added because the live-alarm caller aims this path at
tools that are, by definition, unwell:

- **MinIO write-through cache**, in the SAME prefix and sweep as `msr_image`'s
  (`image_cache/`). A separate prefix would be invisible to the flask_modules
  Airflow DAG that enforces retention office-side, so the two sweeps would
  silently diverge. Keys cannot collide: this one has five path segments
  (`{eqp_ip}/{class_name}/{idw}/{idp}/{name}`) and `msr_image`'s has four, and
  `validate_segment` forbids `/` inside `msr`.
- **`single_flight`**, which `msr_image` already had and this feature did not.
  It collapses concurrent callers — the browser retries a slow image at 2.5s
  and 5s — so a stalled FTP login holds ONE uWSGI worker instead of one per
  arrival. That matters here: `ftp_host_timeout` runs to 60s under a proxy
  harakiri of 75s.

The cache covers the sequential case (a second engineer, an hour later);
`single_flight` covers the simultaneous one. Neither substitutes for the other.

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
  `docs/datatables/hitachi/recipe_idp.txt`.
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
- **`get_param_detail` LISTS the raw folders before planning (2026-08-08).**
  HV-SEM expands one image slot into several stem-suffixed files
  (`IMMS0001-U.jpeg` / `-T` / `-M` / `-L`) that no derivation can predict, so
  the adapter runs `_list_raw_dirs` (one `list_dirs` fleet call, same
  transport) and hands each locator's basenames to
  `rawfiles.slot_sources(slots, listing=...)`. A listing failure is SOFT —
  the plan falls back to the derived `{stem}.jpeg` names (the CD-SEM shape and
  the pre-2026-08-08 behavior); an unreachable host still surfaces as 503 from
  the download step. `slot` is therefore no longer unique in
  `ParamDetailResponse.images` — one entry per FILE, each with its own cond.

### What the 2026-07-30 probe run changed

`scripts/probes/probe_recipe_ftp.py` was run against real files and all five readers'
output is now recorded in `docs/datatables/hitachi/recipe_idp.txt`. Three results
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

Field NAMES live in `docs/datatables/hitachi/recipe_idp.txt` and are expected to change
as the office parser is refined. Nothing in the adapter keys off any of them;
that is what the open key/value `SettingBlock` buys. When they change, the
adapter needs no edit at all — only the mock's tables and that document.

### This screen is read-only

There is no write mode and no plan for one: it displays recipe settings.
`/compare` and `/param-detail` are POSTs only because they take a list body —
`/api/*` allows 50 requests per 5 s, and separate GETs would spend one shared
budget slot per recipe. The adapter writes nothing anywhere: `combined_idp_info` accepts
bytes (user-confirmed 2026-08-05), like the five raw readers, so the `.idp` is
parsed in memory instead of through the temp file this section used to describe.
**Nothing may write to the tool**: these are live metrology recipes on
production equipment.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/recipes

- Handler: `routes.py` → `data.get_recipe_catalog(tool_type, fab_names)`.
  `tool_slug` is `cdsem`/`hvsem`, resolved to `ToolType` (`"cd-sem"`/`"hv-sem"`)
  via `TOOL_BY_SLUG`; `fab_names` comes from `_resolve_fab_names()` — the
  `?fab_name=` query param split on `,`, each part stripped and uppercased,
  empty tuple if the param is blank. `routes.py` passes `fab_names or None`,
  so an empty tuple and an omitted param behave identically (the all-fab
  union).
- Contract: `RecipeSearchResponse` —

  ```python
  class RecipeSearchRow(TypedDict):
      recipe_name: str
      fab_name: str

  class RecipeSearchResponse(TypedDict):
      tool_type: ToolType
      fab_names: list[str]   # echo of the requested fabs; [] on the all-fab union
      total: int
      rows: list[RecipeSearchRow]
  ```

  **Row grain changed from a bare recipe-name string to a `(recipe_name,
  fab_name)` pair (multi-fab phase B, 2026-08-07).** The same recipe name can
  exist on more than one fab — mock cd-sem R3∩M16B overlaps at roughly 20%
  (9,984 of 50,000, user-confirmed 2026-08-07) — so every row now says which
  fab it came from, and the same name on two fabs is two adjacent rows, never
  deduped against each other.
- Mock behavior: for each requested fab (or every fab in `_DEFAULT_FAB_NAMES`
  when `fab_names` is empty), synthesizes 50,000 recipe-name strings
  (`RECIPE_COUNT`) via `_generate_recipe_rows(tool_type, fab)`, seeded from
  `sha256(tool_type:fab)` per fab exactly as before multi-fab — just called
  once per fab and concatenated rather than once per request, so one fab's
  rows are byte-identical whether requested alone or as part of a union.
  Names follow the shape `"<CLASS>/<BASE>_ABC123_<VARIANT>_<00001-suffix>"`,
  cycling through 10 fixed `(class, base)` patterns.
- Office data source: **WIRED.** Redis hash per tool family —
  `v3_cdsem_unique_rcp_list` (cd-sem) / `v3_hvsem_unique_rcp_list` (hv-sem).
  Fields are **lowercase** fab names, values are that fab's recipe-name list
  (`{"m14a": ["1/AC_M2_TAT", ...], "r3": [...]}`). `routes.py` uppercases
  `fab_name`, so the adapter lowercases at the Redis boundary and echoes the
  caller's uppercase spelling back on every row.
  - Fab(s) requested → one `HGET` per fab, each result tagged with that fab
    (`_tagged_rows`). Missing hash *field* (unknown fab) → no rows for that
    one fab, not a whole-request failure. Missing hash *key* → `LookupError`
    (JSON 502): the upstream job never ran.
  - No `fab_name` (blank query — the frontend always sends a fab, so this is
    the blank-query edge case only) → `HGETALL` over every field, and **the
    field name IS the provenance**: each field's rows are tagged with that
    field (lowercase fab, re-uppercased for the row). This replaces the
    pre-multi-fab path, which flattened and deduped the union into bare
    recipe-name strings and destroyed which fab each name came from.
    `_unique` still runs, but only WITHIN one fab's own list (the hash's own
    `*_unique_rcp_list` promise) — never across fabs, since the row grain is
    `(recipe, fab)` and two fabs sharing a name is not a duplicate to collapse.
  - Values parse as JSON, then Python `repr`, then comma-separated, so the
    adapter does not care which the writer job used.
- Notes: per the module docstring, "the office source is expected to return
  only a large Redis-backed recipe-name list" — the office implementation is
  expected to be a plain name lookup, not the full synthetic generator.
  `total` must equal `len(rows)`. **`office_example.py` changed for this
  (multi-fab phase B, 2026-08-07): re-copy at the office** —
  `python -m scripts.adapters.sync_office_adapters recipe_search` (or
  `cp office_example.py office.py`). The boot log's `STALE office.py` line
  flags a pre-2026-08-07 copy, which still answers 200 with bare-string rows
  and a single `fab_name` field the frontend no longer reads.

## Endpoint: GET /api/\<tool_slug\>/recipe-search/recipe-detail

- Handler: `routes.py` → `data.get_recipe_open_data(recipe_id=recipe_name,
  fab_name=fab_name, tool_category=tool_type)`. `recipe_name` is required
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
      fab_name: str
      tool_category: str
      timestamp: str
  ```

  **`fac_id` → `fab_name`, renamed 2026-08-03.** The value never changed —
  `routes.py` always passed `_resolve_fab_name()` into it and both adapters
  immediately re-read it as a fab name — but `fac_id` is device_statistics'
  key, not this feature's (`docs/datatables/README.md`). **An `office.py` copied
  before that date still emits `fac_id`**, which the SPA no longer reads:
  re-copy with `python -m scripts.adapters.sync_office_adapters --force recipe_search`.
  The argument is passed positionally through `data.py`, so a stale copy keeps
  answering — it just answers with the old key.

- Mock behavior: generates all five recipe-open tables for one recipe, seeded
  from `sha256(recipe_id:fab_name:tool_category)` (defaults `"DUMMY_RECIPE_001"`,
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
  hash misses, or `fab_name` is blank, the whole location falls to meas_hist rather
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
  - Parser returns something other than the documented three-key mapping →
    `_normalize_frames` tries to recover the three tables from it by matching
    their **documented columns** (never by position), logging a WARNING that
    names the shape it saw. Only if a table cannot be recognised — or two
    frames answer to the same one — does it raise `LookupError` (502). The
    2026-08-03 cloud failure is why: the old code assumed a mapping in its own
    error message (`sorted(frames)`) and died with a `TypeError` (opaque 500)
    instead of reporting what arrived. See `docs/datatables/hitachi/recipe_idp.txt`
    §파서 반환 구조 — the real shape there is still OFFICE-VERIFY.
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
  Details: `docs/datatables/hitachi/recipe_idp.txt` §집에서의 대역.
- **Where the real `office_utils` comes from, and how to get it back.** The
  office copy is not produced by this repo and is in no commit — `git log
  --diff-filter=A -- 'office_utils/*'` is empty on every branch. If it is
  deleted at the office, git cannot restore it; you re-copy it from its
  original 사내 location.

  | Fact | Value |
  | --- | --- |
  | Source path | **OFFICE-VERIFY** — record it here the next time you copy it |
  | Tracked | never, in either direction (`.gitignore:/office_utils`) |
  | Restore | re-copy from the source above; do **not** copy the home stand-in |

  It survives `reset --hard`, `checkout`, `restore`, and `stash` already —
  those only touch tracked paths. The one command that removes it is `git
  clean` with `-x`/`-X`, which is what happened on 2026-08-03. Two hardenings,
  either or both:

  1. `git init office_utils/` — `git clean -fdx` skips a nested repository
     (`Skipping repository office_utils/`) and needs `-ff` to override.
  2. Keep the package outside the worktree and symlink it in. Imports are
     unaffected (the repo root is `sys.path[0]`), and `clean -fdx` can then
     destroy only the link. Do not park the path entry in
     `.venv/site-packages` — `.venv/` is ignored too, so it is the same
     `clean -fdx` bait.

  If you restore from a reflog or a backup, confirm you got the real parser
  and not the stand-in: the stand-in logs `HOME STAND-IN — 파싱하지 않았음`
  on every call, so that line in an office log means the wrong copy is live.
- Notes: this endpoint mimics "the IDP payload the frontend will request
  after a user chooses one recipe" (module docstring) — unlike `/recipes`,
  the office implementation is expected to assemble real per-recipe detail
  data, not a name-only lookup.

## Endpoint: POST /api/\<tool_slug\>/recipe-search/compare

- Handler: `routes.py` → `data.get_recipe_compare_data(tool_type, recipes)`.
  The request body comes from the frontend compare picker (see
  `front-dev-home` recipe-search compare UI) as JSON:
  `{"recipes": [{"recipe_name": "...", "fab_name": "..."}, ...]}`.
  **Replaces the pre-multi-fab `{"recipe_names": [...], "fab_name": "..."}`
  shape (2026-08-07, no back-compat kept — 사내 consumers only).** `recipes`
  must be a non-empty list of objects (400 if missing/empty/not-a-list),
  each needing a non-blank `recipe_name` (400 otherwise), capped at 200
  entries (400 if exceeded).
- Contract: `RecipeCompareResponse` —

  ```python
  class CompareRequestItem(TypedDict):
      recipe_name: str
      fab_name: str

  class RecipeCompareResponse(TypedDict):
      tool_type: ToolType
      # Distinct fabs of the compared recipes, first-seen order. Replaces the
      # single fab_name now that the request carries one fab per recipe.
      fab_names: list[str]
      recipes: list[CompareRecipe]

  class CompareRecipe(TypedDict):
      recipe_id: str
      fab_name: str
      locator: IdpLocator
      parameters: list[CompareParameter]

  class CompareParameter(TypedDict):
      Parameter: str
      idp: dict[str, object]    # subset of IdpImageInfoRow: COMPARE_IDP_FIELDS
      images: dict[str, str]    # IMAGE_SLOTS key -> filename
  ```

- Mock behavior: for each `{recipe_name, fab_name}` item (blank names
  skipped after `.strip()`), calls `get_recipe_open_data(recipe_id=name,
  fab_name=fab, tool_category=tool_type)` and reshapes its `idp_image_info`
  into a compact per-parameter view — so compare data always matches what
  `/recipe-detail` would return for the same `(recipe, fab)`. **Cross-fab
  compare is the point of this shape**: the same recipe name requested with
  two different `fab_name`s produces two genuinely different generated
  tables, because `get_recipe_open_data` seeds on
  `(recipe_id, fab_name, tool_category)`. `idp` is restricted to
  `COMPARE_IDP_FIELDS` (`Addressing`, `Double_Addressing`, `Mother_Para`,
  `Region`, `Meas_Counting`, `dnumber_removed`); `images` maps each
  `IMAGE_SLOTS` key to that parameter's slot value, which the client posts
  straight back as `/param-detail`'s `slots`. AMP is not part of this
  payload — compare fetches it per visible cell, so the two screens cannot
  disagree. Each recipe carries its own `locator`, because those fetches are
  per tool. Duplicate `Parameter` values within one recipe's
  `idp_image_info` are de-duplicated (first occurrence wins). The response's
  `fab_names` is the distinct set of *resolved* `detail["fab_name"]` values,
  first-seen order — not a verbatim echo of the request body, since a blank
  `fab_name` in an item resolves through `get_recipe_open_data`'s own
  default.
- Office data source: **NOT WIRED — mock-backed**, and now the only endpoint
  that is. Re-exported (not reimplemented) so that when the batched IDP fetch
  lands it can be derived from open rather than growing a second data path.
  Until then compare disagrees with `/recipe-detail` for the same recipe;
  see Status above. Because it is a re-export rather than a separate
  implementation, it already speaks the new `recipes: [{recipe_name,
  fab_name}]` body with no adapter change of its own — office risk here is
  unchanged by multi-fab phase B.
  <!-- OFFICE: same IDP payload source as /recipe-detail, batched per recipe -->
- Notes: `get_recipe_compare_data` reuses `get_recipe_open_data` internally
  "so compare matches open" (source comment) — an office implementation
  should preserve that invariant (compare output for a recipe should be
  derivable from / consistent with that recipe's `/recipe-detail` output)
  rather than hitting a separate data path that could drift.

## Endpoint: POST /api/\<tool_slug\>/recipe-search/registry-check

`check_recipe_registry(tool_type, recipes) -> RegistryCheckResponse` — one
result per requested `(recipe_name, fab_name)`, **positionally**, since the same
name legitimately appears under two fabs.

The office adapter calls `_locate_via_redis` and **must not** call
`_locate_idp`. That is the whole contract:

- `_locate_via_redis` answers "the registry can place this recipe", from
  `v3_{family}_rcp_loc_{fab}` and `v3_{family}_tools_in_rcp_{fab}` — two hash
  reads, no OpenSearch. Registry-backed is a strict **subset** of locatable.
- `_locate_idp` also falls back to measurement history. An adapter that used it
  would report `in_registry: true` for a recipe only a measurement RUN can
  place, and the frontend would unlock 열어 보기 and compare on that basis.

`reason` carries `_locate_via_redis`'s own bail note, joined the way
`_locate_idp` joins it into its 502, and is empty exactly when `in_registry` is
true. It is the only way a home or cloud caller can tell "this fab has no
registry hash" from "the hash does not name this recipe".

**Why the endpoint exists.** The frontend was inferring recipe capability from
membership in the daily catalog list (`/recipes`). The catalog hash and the
location registry are written by different upstream jobs, so the inference is
wrong in both directions: a registered recipe absent from the list had
recipe-open refused for no reason, and a listed recipe that has never run nor
been registered had it offered and then 502'd. This asks the registry the
question the inference was standing in for.

**Cost, and the one thing to watch.** Two `hget`s per recipe plus one
`_eqp_ip_index()` — ttl-cached, so a batch pays the sem_list roster once rather
than once per recipe. The two `hget`s are NOT batched: they are issued through
`_locate_via_redis` one recipe at a time, so a full page costs 2N sequential
round trips. That is deliberate — one code path answers "can the registry place
this recipe", and a second, batched reader would be free to drift from the one
recipe-open actually uses. It is also the first time `_locate_via_redis` runs in
a loop inside one request, so the cost is new even though the function is not.

The frontend sends only the OpenSearch-fallback rows of the visible page, which
is normally a handful; the ceiling is 100 (its page size), not the 200 the route
allows. If a real batch ever gets big enough to feel, the fix is `HMGET` grouped
by fab — the batch shares a fab in the common case, so `2 × distinct_fabs`
round trips replace `2 × N` — and it belongs INSIDE `_locate_via_redis` as a
plural entry point, so both callers keep reading the same registry logic.

## Endpoints: the tiered reads (2026-08-02) — no adapter work

`GET /parameters`, `GET /measurement-points` and `GET /param-info` are
**composed**, not implemented: `param_info.py` calls
`data.get_recipe_open_data()` and `data.get_param_detail()` and reshapes their
output. Nothing in `providers/` changes, there is no new swap surface, and both
adapters answer all three the moment the routes exist. There is nothing to `cp`
at the office for these.

- `/parameters` — `ParameterListResponse`. Every `idp_image_info` row verbatim
  plus `total_rows`, `distinct_parameters`, `mother_rows`, `addressing_rows` and
  the `locator`. A strict, cheaper subset of `/recipe-detail`, for callers that
  want the parameter listing without the measurement and align tables.
- `/measurement-points` — `MeasurementPointsResponse`. `wafer_mp_info` filtered
  to one `parameter` (required; 404 when the recipe has no row naming it).
- `/param-info` — `ParamInfoResponse`. `occurrences[]`, one per
  `idp_image_info` row naming the parameter, each with `amp`, `af_pr` and
  `images[].cond` flattened from `SettingBlock` to rows plus a `*_source`.

**Cost note for the office.** Each of the three calls `get_recipe_open_data`,
which office-side is locate + an FTP download of the `.idp` + parse, and that
function deliberately caches nothing (its docstring: *"a recipe's .idp is
small … if 열어보기 latency ever becomes a complaint this is still the seam to
put a TTL cache behind"*). These endpoints change that calculus: a script that
walks a recipe parameter by parameter now pays one `.idp` download **per
call**, on top of the raw-folder session. The catalog copy steers bulk callers
to `parameters` once followed by `POST param-detail`, which needs the locator
only once. If a real bulk consumer appears, the TTL cache at that seam — keyed
on the recipe triple — is the fix, not a change here.

Two things an office adapter must not break:

- **`include=` narrows the READ, not the response.** It works by dropping slots
  from the `slots` dict handed to `get_param_detail`, and `rawfiles.slot_sources`
  reads every slot with `slots.get(...)`, so an absent key takes the same branch
  as an empty one and that file is never fetched. An adapter that stops planning
  its reads through `slot_sources` turns `include=` into cosmetic filtering that
  still costs a full FTP session.
- **One returned entry per requested item.** `build_param_info` zips the rows
  against `get_param_detail`'s output with `strict=True`, so a count mismatch
  raises rather than silently dropping occurrences.

## Verify

    SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/recipe_search

## 502 진단 (`/recipe-detail`)

`자세히 보기`가 502 를 반환할 때는 `.idp` 위치를 찾지 못한 것입니다. 위치 소스는
Redis 레지스트리와 meas_hist 두 개이므로 502 는 **둘 다 실패했다**는 뜻입니다.
브라우저에 보이는 문장은 meas_hist 만 지목하지만, 측정된 적 없는 recipe 에서
meas_hist 가 비어 있는 것은 정상이며 레지스트리가 바로 그런 recipe 를 위해
존재합니다. 따라서 실제로 물어야 할 것은 "레지스트리가 왜 답하지 않았는가"이고,
아래 스크립트가 두 소스의 각 단계를 순서대로 확인합니다.

    .venv/bin/python -m scripts.diagnose.diagnose_recipe_search_office "1/AC_M2_TAT" --fab R3

읽는 법 — 502 본문에 `Redis recipe registry was tried first and declined: ...`
절이 있으면 배포된 `office.py` 가 레지스트리를 조회했고 그 이유를 말해 줍니다.
**그 절이 없으면** 배포본이 레지스트리 경로가 없던 시절의 STALE 사본이므로
Redis 를 아예 조회하지 않은 것입니다. 이때는 데이터가 아니라 사본을 고칩니다.

    python -m scripts.adapters.sync_office_adapters recipe_search
