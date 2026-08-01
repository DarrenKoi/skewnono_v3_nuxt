# Recipe-open parameter — Excel export and tiered read API — Design

- **Date:** 2026-08-02
- **Status:** approved
- **Area:** `recipe_search` recipe-open — new read endpoints, `/endpoints`
  catalog, frontend Excel export

## Problem

A user looking at one parameter on `/ebeam/{tool}/{fab}/recipe-search/open` can
see everything about it — the `idp_image_info` row, AMP, AF/PR, each image and
its beam condition — and can take **none** of it with them. There is no
download, and there is no documented way to ask for the same data from a
script.

Both gaps have a shape the codebase already knows how to fill, and both have a
trap in them.

**The export trap.** `recipe-compare` already exports an `.xlsx`
(`utils/recipeCompare.ts`, `exceljs`). Its image handling is a deliberate
non-answer:

> The image FILENAMES, not the images. Until 2026-07-29 this stamped a
> browser-rendered fake SEM texture into the sheet — harmless while every other
> column was fabricated too, actively misleading now that they are real tool
> data. Embedding the genuine images would mean pulling each one off the tool's
> FTP server at export time; the names let a reader find them without that cost.

That reasoning is sound **for compare**, which is N recipes wide. It does not
carry over to one parameter, which has at most three image slots
(`rawfiles.IMAGE_SLOT_KEYS`). Reusing compare's answer here would ship a
filenames-only export for a case whose cost objection does not apply.

**The API trap.** `POST param-detail` already returns the deep data, but its
body requires the `locator` **and** the five `img_*` slot values. A browser has
both because `recipe-detail` returned them; a script starting from a recipe name
has neither. It must call `recipe-detail`, dig `locator` out of the payload,
find the matching `idp_image_info` row, extract five columns, and post them
back. None of that is documented — the `Recipe Search` group of
`/endpoints` lists `recipes`, `recipe-detail`, `lateral`, `meas-hist` and
`msr-file`, and omits `param-detail`, `align-detail` and `recipe-image`
entirely.

There is a third trap under both of them.

**A parameter is not a row.** A row of `idp_image_info` is one image
*definition*. `Para_13` legitimately appears twice in one recipe, at SEQ 4/6 and
SEQ 11/15, resolving to `IMMP0004…` and `IMMP0011…`. This has already caused one
silent wrong-answer bug — a cache keyed on the parameter name alone served the
first row's images under the second row's heading, recorded at
`useRecipeParamDetail.ts:83`. Any new API that returns "the parameter's detail"
as a single object reproduces that bug for every caller.

## Cost model

Two data sources hide behind "parameter info", and they differ by orders of
magnitude:

| Source | Read cost | Fields |
| --- | --- | --- |
| `.idp` parse | already in hand from `recipe-detail`; no extra I/O | `idp_image_info`, `wafer_mp_info`, `locator` |
| raw-recipe folder | up to **5 FTP file reads per occurrence**, off the measuring tool itself | `amp`, `af_pr`, each image's `cond` |

`useRecipeParamDetail.ts` states the consequence: settings are fetched on click
"because each parameter costs up to five files off the measuring tool's own FTP
server and most parameters are never opened."

Serving both tiers from one endpoint would make every list-browsing script pay
the deep tier's price against a production tool. The endpoint family below is
split on exactly this boundary.

## Design — API

Three new endpoints under `/api/{tool_slug}/recipe-search/`. All are `GET`, all
are token-callable, and all are ordered cheap-first in the catalog.

### Tier 0 — `parameters`

`GET /api/{tool_slug}/recipe-search/parameters?recipe_name=&fab_name=`

Zero FTP. Returns `idp_image_info` **verbatim, one entry per row** — the same
grain the table on the left of the page renders — plus recipe-level roll-ups and
the `locator`.

```jsonc
{
  "recipe_id": "RCP_001",
  "fab_name": "M11",
  "tool_type": "cd-sem",
  "locator": { "eqp_ip": "…", "class_name": "…", "idw": "…", "idp": "…" },
  "total_rows": 34,
  "distinct_parameters": 28,
  "mother_rows": 3,
  "addressing_rows": 21,
  "rows": [
    { "Parameter": "Para_13", "SEQ": 4, "Last_SEQ": 6, "Region": 1,
      "Addressing": true, "Mother_Para": true, "Double_Addressing": false,
      "Meas_Counting": 5, "dnumber_removed": false,
      "img_add1": "IMMP0004", "img_add2": "PRMP0000",
      "image_add3": "non", "img_meas1": "IMMS0000", "img_meas2": "PRMS0000" }
  ]
}
```

Three decisions here:

- **`total_rows`, never `total`.** With per-row grain a bare `total` is the
  field a caller misreads as a parameter count. `distinct_parameters` is carried
  beside it so the number a user actually wants needs no client-side dedup.
- **`mother_rows` / `addressing_rows` are row counts too**, named to say so.
- **The `locator` is returned.** A caller that wants bulk deep data can drop
  straight into `POST param-detail` with the rows it just received, without a
  second `recipe-detail` call. This endpoint is a strict, cheaper subset of
  `recipe-detail`; it does not replace it.

### Tier 1 — `measurement-points`

`GET /api/{tool_slug}/recipe-search/measurement-points?recipe_name=&parameter=&fab_name=`

Zero FTP. `wafer_mp_info` filtered to `Parameter == parameter`, verbatim.

Its own endpoint rather than a field of the others because it is a different
grain (one row per measurement point, tens per parameter) and the one part a
script may plausibly want in bulk. `parameter` is required — the unfiltered set
is what `recipe-detail` already returns.

### Tier 2 — `param-info`

`GET /api/{tool_slug}/recipe-search/param-info?recipe_name=&parameter=&fab_name=&include=`

The FTP-backed tier.

```jsonc
{
  "recipe_id": "RCP_001", "fab_name": "M11", "tool_type": "cd-sem",
  "parameter": "Para_13",
  "locator": { … },
  "occurrences": [
    { "idp": { "SEQ": 4, "Last_SEQ": 6, "Region": 1, "Addressing": true, … },
      "amp":    [ { "key": "…", "value": "…" } ],
      "af_pr":  [ { "section": "…", "key": "…", "value": "…" } ],
      "images": [ { "slot": "img_add1", "stage": "Addressing 1",
                    "name": "IMMP0004.jpeg",
                    "cond": [ { "key": "…", "value": "…" } ] } ] }
  ]
}
```

**`occurrences` is a list because a parameter is not a row.** A single-object
response would have to pick one row silently and reproduce the
`useRecipeParamDetail.ts:83` bug for every caller. The page's export writes only
the selected row's occurrence — the page knows which row was clicked; a script
does not, so it gets all of them.

**`include=amp,af_pr,images`** (default: all three) selects which parts are
built. It is implemented by **trimming the `slots` dict** handed to
`get_param_detail`, not by filtering the response:

| `include` omits | slot dropped from the request | reads skipped |
| --- | --- | --- |
| `amp` | `img_meas2` | the `PRMS…` → AMP read |
| `af_pr` | `img_add2` | the `PRMP…` → `ENMP…` read |
| `images` | `img_add1`, `image_add3`, `img_meas1` | up to 3 image `cond.txt` reads |

Both adapters plan their reads through the same `rawfiles.slot_sources`
(`providers/mock.py:932`, `providers/office_example.py:1209`), and that planner
reads every slot with `slots.get(...)` — so an **absent** key already behaves
exactly like an empty one, and a dropped slot is a read that never happens. This
is what makes `include=` a real cost control rather than cosmetic filtering, and
it needs **no provider change**: the branch it takes is one both adapters
already take for the ordinary `non` case.

Note that omitting `images` drops image **names** as well as conditions. That is
acceptable: the names are columns of the tier-0 payload, which costs nothing.

`amp`, `af_pr` and `images[].cond` are flattened from `SettingBlock` to a plain
row list, with the block's `source` moved onto the occurrence as
`{part}_source`. A caller wanting the block shape verbatim uses `param-detail`.

### Errors

- `400` — `tool_slug` not `cdsem`/`hvsem`; `recipe_name` or `parameter` missing;
  `include` naming an unknown part.
- `404` — the parameter is absent from the recipe. Distinct from an empty
  `occurrences`, which cannot occur.
- `503` — the tool is unreachable, via the existing `MsrImageError` → `_error()`
  path already used by `param-detail`, `align-detail` and `recipe-image`.
- `occurrences` is capped at `_MAX_PARAM_ITEMS` (200), the existing cap. An
  unbounded parameter match is an unbounded pull off a production tool.

### Placement

Composition lives in a new `recipe_search/param_info.py`, calling
`get_recipe_open_data()` and `get_param_detail()` from `data.py`. `routes.py`
stays a validate-and-dispatch layer.

**No provider work at all.** Nothing new touches `providers/`, so mock and
office both answer the moment the route exists. There is no new swap surface, no
`office_example.py` change, and no `cp` to perform at the office. `MIGRATION.md`
gains a line recording that.

## Design — `/endpoints` catalog

`app/pages/endpoints.vue` is a hand-maintained catalog. The `Recipe Search`
group gains six entries, ordered cheap → expensive:

| Entry | Why |
| --- | --- |
| `GET parameters` | new |
| `GET measurement-points` | new |
| `GET param-info` | new |
| `POST param-detail` | shipped, undocumented — the bulk path |
| `GET align-detail` | shipped, undocumented |
| `GET recipe-image` | shipped, undocumented; `response: image/*` |

`recipe-image` returns bytes, so its entry states that rather than naming a
TypedDict — the page already has an `image/svg+xml` precedent in the AFM group.

## Design — Excel export

### Control

A split button in the `SELECTED` header of `RecipeOpenView.vue`, on the row
carrying the parameter name and the `MOTHER`/addressing pills. It acts on the
parameter as a whole, so it does not belong to any one tab.

- Main click — text + **측정 이미지** (`img_meas1`), embedded.
- Dropdown — the same plus the two **Addressing** images (`img_add1`,
  `image_add3`).

측정 이미지 is unconditional: there is no text-only variant. Addressing images
are opt-in because they are two of the three FTP reads and are the ones a reader
most often does not need.

Disabled while `paramPending`. Shows a spinner while running — embedding pulls
images off the tool, so it is not instant. A slot holding `non`, or an image the
tool 404s, is written as a `없음` label in place of the picture rather than
failing the export.

### Workbook

Filename `{recipe_id}_{parameter}.xlsx`. Four sheets:

| Sheet | Contents |
| --- | --- |
| `개요` | The selected `idp_image_info` row — Region, SEQ, Last_SEQ, Meas_Counting, the three flags, `dnumber_removed` — plus `recipe_id`, fab, tool, the locator, and an export timestamp |
| `AMP` | `paramDetail.amp` rows, `key`/`value`, reader order preserved |
| `AF_PR` | `paramDetail.af_pr` rows as **`section` / `key` / `value`** |
| `이미지` | Per included slot: stage, filename, the embedded picture, and that image's `cond` rows beneath it |

`AF_PR` gets three columns rather than the compare export's flattened
`section.key` label because a row's identity is `(section, key)`: two addressing
passes carry the same inner keys, and a flat label makes them indistinguishable
without string surgery. Compare flattened only because its sheet is a matrix.

`측정 위치` (`wafer_mp_info`) is **not** a sheet. It is a different grain, the
on-screen tab itself calls it "자주 보지 않는 정보", and its row count varies
independently of everything else in the file. It is reachable through the
`measurement-points` endpoint.

### Placement

A new `app/utils/recipeParamExport.ts`:

- `buildParamWorkbook()` — pure, `node --test`-able, returns the sheet model.
- `downloadParamWorkbook()` — `exceljs`, image fetches, blob download.

Deliberately not added to `utils/recipeCompare.ts`: that file is already ~380
lines and its builder is shaped around the N-recipes-wide matrix, which this is
not. Image bytes come from the existing `recipe-image` endpoint via
`recipeImageUrl()` — no new backend surface for the export.

## Testing

Backend, `back_dev_home/ebeam/hitachi/recipe_search/tests/`:

- a parameter with two occurrences returns two `occurrences`, in row order,
  with different image names;
- unknown parameter → 404; missing `recipe_name`/`parameter` → 400; bad
  `include` → 400;
- `include=amp` omits `af_pr` and `images` **and** drops `img_add2` and the
  three image slots from the request reaching the provider;
- an unreachable tool → 503 rather than a 500 traceback;
- tier-0 roll-ups: `total_rows` counts rows and `distinct_parameters` counts
  parameters on a fixture where they differ;
- `measurement-points` filters by `Parameter` and 404s on an unknown one.

Frontend, `node --test`:

- `buildParamWorkbook()` sheet names, `AF_PR`'s three columns, `개요` field set,
  and that an excluded slot produces no `이미지` block.

Image embedding is browser-only and has no automated harness — there is no E2E
suite in this repo. It is verified by hand through the `verify` skill.

## Out of scope

- Exporting more than one parameter at once. `recipe-compare` already owns the
  multi-parameter workbook.
- Embedding align images. They belong to the recipe, not to a parameter, and
  `align-detail` already serves them.
- Changing `POST param-detail`'s shape. It stays the bulk path, now documented.
