# Raw-recipe folder — real AMP, focus/PR and beam conditions — Design

- **Date:** 2026-07-29
- **Status:** approved
- **Area:** `recipe_search` recipe-open and recipe-compare — backend contract, new
  endpoints, FTP path layer, mock, home parser stand-in, frontend

## Problem

Two keys of `RecipeDetailResponse` are invented. Not "mock-only" invented —
invented **at the office too**, on a live production screen. `office_example.py`
says so in its own docstring:

> `align_images` and `amp_info` — FABRICATED, even at the office. Neither is
> among `combined_idp_info`'s three keys. The screen already draws both, so they
> are generated rather than dropped, and this function exists to keep exactly one
> place to delete when a source turns up. The candidate is the raw-recipe folder
> beside the `.idp` (`data/{idw}/{idp}/`), which a second 사내 parser is expected
> to read.

That guess was right on both counts. The source **is** the raw-recipe folder, and
a second parser — `office_utils/idp_amp_reader.py` — **does** read it. The
preceding spec (`2026-07-28-idp-image-info-boolean-columns-design.md`) closed
with "parse the raw-recipe folder for `amp_info`" as its first open item. This
spec answers it.

Three consequences follow, and all three are corrected here:

1. **`AmpRow`'s sixteen optical fields are fiction.** `Mag`, `Vacc`, `I_probe`,
   `Frame`, `Scan`, `WD`, `Det`, `Template`, `MatchScore`, `SearchArea`,
   `Rotation`, `Algo`, `ROI`, `EdgeThr`, `EdgeDir`, `Smooth` were named at home
   and have never been compared against a real file.
2. **The mock teaches a false naming convention.** It emits
   `IMG_ADD1_0001.jpg`; the office emits `IMMP0001`. Any path arithmetic written
   against the mock would be untestable and wrong — the exact failure
   `docs/datatables/recipe_idp.txt` warns about in its header
   (*"컬럼 이름이 어긋나면 집에서는 통과하고 사무실에서만 깨진다"*), reached
   through values instead of names.
3. **Compare diffs fabricated numbers.** `CompareMatrix.vue:120` builds its AMP
   diff from the same `_sourceless_extras()` output.

## What the office confirmed (user-confirmed 2026-07-29)

### Column value formats

Every `img_*` value is an 8-character name, `{kind}{stage}{NNNN}`, with no
extension:

| Column | Example | Kind | Stage | Carries |
| --- | --- | --- | --- | --- |
| `img_add1` | `IMMP0001` | `IM` image | `MP` | addressing image 1 |
| `img_add2` | `PRMP0000` | `PR` | `MP` | key to the AF/PR setting file |
| `image_add3` | `I2MP0000` | `I2` image | `MP` | addressing image 3 |
| `img_meas1` | `IMMS0000` | `IM` image | `MS` | measurement image |
| `img_meas2` | `PRMS0000` | `PR` | `MS` | the AMP setting file itself |

`AP` is the third stage, used by wafer align: `IMAP0001` / `ENAP0001`.

### Rules

1. **`"non"` is the empty sentinel** — French `non`, **not** `"none"`. A slot
   holding `"non"` has no file; no FTP call is made for it.
2. **Condition sidecars live in a `.`-prefixed hidden directory.** The image
   `IMMP0001.jpeg` is a file; `.IMMP0001.jpeg/` is a sibling directory holding
   `cond.txt`. This is not new — `msr_image/paths.py:40` already implements
   exactly this (`office 확인 2026-07-24`) and `cond_path()` is reused verbatim.
3. **`PR` → `EN` gives the AF/PR setting file.** `img_add2 = "PRMP0000"` →
   `ENMP0000`. The first two characters are always `PR`.
4. **`img_meas2` is used as-is.** `PRMS0000` is the AMP file's own name; it is
   *not* `PR`→`EN` translated.
5. **Setting files (`EN…`, `PR…`) have no extension.** Only images carry
   `.jpeg`.
6. **Numbering is zero-padded to four digits.** `ENAP{p:04d}`, so `P.No = 1` is
   `ENAP0001`. The literal concatenation `"ENAP000" + str(p)` in the original
   description breaks at `p = 10`; four-digit padding is the rule.
7. **`img_add2` yields no image.** It is a setting key only. Likewise
   `img_meas2`.

### The reader

`office_utils/idp_amp_reader.py`, office-only and gitignored like the rest of
`office_utils/`. Three functions, each accepting a **path, bytes, or string**:

| Function | Reads | Reached from |
| --- | --- | --- |
| `read_amp_info` | `PRMS0000` | `img_meas2` |
| `read_af_pr_condition` | `ENMP0000`, `ENAP0001` | `img_add2` (PR→EN), align |
| `read_meas_image_condition` | `.{image}.jpeg/cond.txt` | every image slot, align |

Accepting bytes is what allows the whole pipeline to run without writing a
single byte to the Flask host. (`read_idp_info.combined_idp_info` takes a path
only, so the `.idp` itself still lands on disk — unchanged from today.)

**OFFICE-VERIFY:** the field names each reader returns are not yet known. The
contract below is therefore *open* key/value, which is the honest shape: an
unknown key renders instead of vanishing. When the real names arrive only the
mock and `recipe_idp.txt` change — not the contract, not the frontend.

## File map

With `raw = /HITACHI/DEVICE/HD/{class_name}/data/{idw_stem}/{idp_stem}` —
the folder `probe_recipe_ftp.py` already derives as `raw_dir` and lists at stage
[4] without downloading:

| Source | Value | Image | Setting / condition |
| --- | --- | --- | --- |
| `img_add1` | `IMMP0001` | `{raw}/IMMP0001.jpeg` | `{raw}/.IMMP0001.jpeg/cond.txt` |
| `img_add2` | `PRMP0000` | — | `{raw}/ENMP0000` |
| `image_add3` | `I2MP0000` | `{raw}/I2MP0000.jpeg` | `{raw}/.I2MP0000.jpeg/cond.txt` |
| `img_meas1` | `IMMS0000` | `{raw}/IMMS0000.jpeg` | `{raw}/.IMMS0000.jpeg/cond.txt` |
| `img_meas2` | `PRMS0000` | — | `{raw}/PRMS0000` |
| `P.No` = p | — | `{raw}/IMAP{p:04d}.jpeg` | `{raw}/.IMAP{p:04d}.jpeg/cond.txt` and `{raw}/ENAP{p:04d}` |

Align points are the **sorted unique** `P.No` values of `wafer_align_info`.

## Approach

### 1. The locator travels to the client

`/recipe-detail` already resolves `recipe_name` → `{eqp_ip, class_name, idw,
idp}` through OpenSearch (`office_example.py:_locate_idp`) and then discards it.
It now **returns** it, and every follow-up request passes it back.

This mirrors `msr_image`, where the client holds `eqp_ip/class_name/msr` and
sends them on each image GET. The payoff is that no follow-up call re-downloads
or re-parses the `.idp` — the expensive step happens exactly once per recipe
open.

The cost is that the client names FTP paths, so every client-supplied segment
goes through the existing `validate_tool_ip()` and `validate_segment()` guards.
Those already exist for precisely this reason.

### 2. `recipe_search/rawfiles.py` — pure path arithmetic, zero I/O

```text
raw_dir(locator)                        -> "/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}"
image_name("IMMP0001")                  -> "IMMP0001.jpeg"        ("non" -> None)
setting_name("PRMP0000", pr_to_en=True) -> "ENMP0000"
setting_name("PRMS0000")                -> "PRMS0000"
align_names(1)                          -> ("IMAP0001.jpeg", "ENAP0001")
cond_path(...)                          -> reused from msr_image.paths
```

Keeping this pure and separate is the central testability decision. Naming is
the part most likely to be wrong and it is unverifiable from home against a live
tool — so it is isolated into a module that needs no tool at all. This is the
same reasoning that already put `_to_detail_response()` on its own: *"Everything
unreachable from home is upstream of this function, which is why it is separate:
the mapping it performs is the part most likely to be wrong, and this way it is
the part that can be tested anywhere."*

### 3. Endpoints

| Method | Path | Returns |
| --- | --- | --- |
| GET | `…/recipe-detail` | three tables **+ `locator`** |
| POST | `…/param-detail` | `{items: [{locator, parameter, slots}]}` → `list[ParamDetailResponse]` |
| GET | `…/align-detail?{locator}` | every unique `P.No` at once |
| GET | `…/recipe-image?{locator}&name=IMMP0001.jpeg` | `image/jpeg` bytes |

`param-detail` is a **POST taking a list**, not a GET, for one concrete reason:
`/api/*` is rate-limited to 20 requests / 5 s per user. Compare viewing a single
cell across 20 recipes would trip that immediately as 20 GETs; as one POST it is
one request. The open screen sends a one-element list, so both screens share the
endpoint. `…/compare` is already a POST, so this is consistent rather than novel.

Images stay GET so the browser's own cache absorbs repeat views —
`Cache-Control` copied from `msr_image`'s serve route. **Changed during
implementation** to `public, max-age=31536000, immutable` rather than
`max-age=3600`: a raw-recipe file cannot change for a given recipe, and at one
hour every thumbnail costs a fresh FTP session to a production tool. Nothing is
stored on the Flask host: bytes go FTP → memory → `Response`.

Per parameter click that is **one** `param-detail` POST plus lazy `<img>` GETs as
thumbnails come into view. The POST fetches at most five files in a single
batched FTP session — `PRMS0000`, `ENMP0000`, and one `cond.txt` for each of the
three image slots — and fewer whenever a slot holds `"non"`.

`slots` in the request body is the row's five `img_*` values verbatim, as the
client already received them in `idp_image_info`. The server does not re-parse
the `.idp` to recover them.

### 4. Contract

```python
SettingRow   = TypedDict("SettingRow", {"key": str, "value": str})
SettingBlock = TypedDict("SettingBlock", {
    "source": str,                 # "PRMS0000" — the file it came from
    "rows": list[SettingRow],      # the reader's own key order, preserved
})

ParamImage = TypedDict("ParamImage", {
    "slot": str,                   # img_add1 | image_add3 | img_meas1
    "stage": str,                  # "Addressing 1" … — from IMAGE_SLOTS
    "name": str,                   # "IMMP0001.jpeg" — feed to recipe-image
    "cond": SettingBlock | None,
})

ParamDetailResponse = TypedDict("ParamDetailResponse", {
    "parameter": str,
    "amp": SettingBlock | None,    # img_meas2 -> read_amp_info
    "af_pr": SettingBlock | None,  # img_add2 -> EN… -> read_af_pr_condition
    "images": list[ParamImage],
})

AlignPoint = TypedDict("AlignPoint", {
    "P_No": int,
    "image": str | None,           # "IMAP0001.jpeg"
    "cond": SettingBlock | None,
    "setting": SettingBlock | None,  # ENAP0001
})
AlignDetailResponse = TypedDict("AlignDetailResponse", {"points": list[AlignPoint]})
```

**Removed:** `AmpRow`, `AlignImageRow`, `RecipeDetailResponse.amp_info`,
`RecipeDetailResponse.align_images`, `CompareParameter.amp`, and
`_sourceless_extras()` itself — which is the deletion its docstring asked for.
`generate_amp_info()` and `generate_wafer_align_images()` go with it.

**Added:** `locator` on `RecipeDetailResponse` and on each `CompareRecipe`.

Row order is the reader's own. Nothing sorts or renames keys, so a field the
office adds appears on screen without a code change.

### 5. Compare goes lazy too

`CompareMatrix.vue` already scopes its view to one `(parameter, slotKey)` pair,
so a visible cell needs AMP for *N recipes × 1 parameter* — one `param-detail`
POST carrying N items. Browsing never fetches the full cross-product, so the
200-recipe cap stays reachable.

**One exception, added during implementation:** the xlsx export covers every
*selected* parameter, not just the visible cell, so it does fetch the
cross-product — minus whatever browsing already cached, and chunked across
requests because the server caps one POST at 200 items. Nothing on screen
triggers it; only pressing 내보내기 does.

The alternative — leaving compare on fabricated AMP — was rejected: the same
recipe would then show real settings on the open screen and invented settings on
compare. Today's all-fabricated state is at least uniform; a half-real one is
actively misleading.

### 6. Errors

| Situation | Behaviour |
| --- | --- |
| Slot is `"non"` or empty | No FTP call at all; slot renders 없음 |
| File absent on FTP | Block is `None`, HTTP **200**, panel shows 파일 없음 |
| Reader raises on a real file | Block is `None`, warning logged with the filename |
| FTP host/session failure | **503** (see note) |
| Image absent | HTTP **404** |

A missing file is normal here, not a failure — parameters legitimately lack
addressing images or AF/PR settings, and a recipe with two `"non"` slots is
healthy. Only the transport failing is an error.

**Implementation note (2026-07-29):** this section originally said 502. The code
raises `msr_image.errors.SourceUnavailable`, which is **503** — reusing the
sibling feature's existing error hierarchy beat minting a second convention on
the same tool-FTP surface. The signal is `HostFailure.remote_path is None`
(connect/login/listing failed), *not* "no file came back": a parameter can
legitimately request only a `cond.txt` that does not exist, and counting that as
an outage would report a healthy tool as down. The image case returns a real
404 rather than a JSON body so `<img>` falls back to its own broken-image state
instead of trying to decode an error message as a picture.

### 7. Home: mock and stand-in

The office facts above land in code as well as in this document, per CLAUDE.md's
two-places rule.

- **`providers/mock.py`** — `generate_idp_image_info()` switches to the real
  naming convention (`IMMP0001`, `PRMP0000`, `IMMS0000`, `PRMS0000`, `I2MP0000`)
  and emits `"non"` on some slots so the no-file path is exercised at home. New
  `get_param_detail()` / `get_align_detail()` / image bytes, seeded off
  `(recipe, parameter)` so refreshes are stable. Values stay plainly fabricated;
  only the *shape and naming* imitate the office.
- **`office_utils/idp_amp_reader.py`** — a new gitignored home stand-in
  mirroring `read_idp_info.py`: the same three signatures, accepting
  path/bytes/str, returning fabricated key/value rows seeded off the input, with
  a docstring stating outright that it parses nothing. Without it the office
  adapter cannot be imported — let alone run — at home.
- **Mock images** reuse `msr_image`'s seeded-SVG placeholder (`_svg()`), which
  returns `image/svg+xml` so the browser renders something without pretending to
  be a SEM photograph.

### 8. Frontend

| File | Change |
| --- | --- |
| `useRecipeSearchApi.ts` | Drop `amp_info`/`align_images`; add `locator` |
| `useRecipeParamDetail.ts` | New — POST, `useAsyncData`-cached per `(recipe, parameter)` |
| `AmpBlock.vue` | Fixed 16-column matrix → key/value rows from `SettingBlock` |
| `ImgThumb.vue`, `ImageLightbox.vue` | `src` → `…/recipe-image?…` |
| `AlignPopup.vue` | Fetch `align-detail` on open |
| `CompareMatrix.vue` | Fetch the visible cell's row across recipes in one POST |

Colours come from `--sk-*` tokens only; `DESIGN.md` governs, as always.

### 9. Testing

- `rawfiles.py` gets full pure unit coverage at home: every slot's naming, the
  `"non"` sentinel, `PR`→`EN`, four-digit padding, and `cond_path` composition.
- Provider-contract tests assert mock and office return the same TypedDict
  shapes, through the existing parity harness.
- Frontend `node --test` covers pure name helpers only — there is no mounting
  harness and no E2E suite. Browser checks go through the `verify` skill.

## Out of scope

- **Caching the FTP round-trip.** Option B from the design discussion —
  reusing `msr_image`'s disk/MinIO cache — is deliberately deferred. Recipe open
  pulls ~5 images per click, not the hundreds the gallery pulls, and the browser
  cache already absorbs repeats. The endpoint shape is chosen so this can be
  added later with **zero frontend change**.
- **`Region = P_No` as a replacement for the `Parameter` join.** Carried over
  unresolved from the 2026-07-28 spec.
- **What `D_No = -1` renders as.** Same.

## Open items

1. **The readers' real field names** (OFFICE-VERIFY). The user is checking. The
   open key/value contract holds regardless; only the mock's fabricated keys and
   `recipe_idp.txt` need updating when they land.
2. **Whether `ENAP{p:04d}` files exist for every `P.No`,** or only for points
   with a stored condition. The design treats absence as normal, so a wrong
   assumption here degrades to 파일 없음 rather than an error.
3. **Whether `img_add2`'s `PRMP…` file itself holds anything useful.** The user
   reports finding nothing extractable from it so far; only its `EN…` translation
   is read.

## Documentation

`docs/datatables/recipe_idp.txt` gains a raw-recipe-folder section carrying the
naming table, the `.`-prefixed sidecar rule, the `"non"` sentinel, four-digit
padding and the extensionless setting files, marked `user-confirmed 2026-07-29`.
`recipe_search/MIGRATION.md` gains the new office-adapter obligations.
