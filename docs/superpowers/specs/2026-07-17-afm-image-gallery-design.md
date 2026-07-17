# AFM Additional-Image Gallery — Design Spec

Date: 2026-07-17
Status: Approved (brainstorming), pending implementation plan
Scope: Sub-project **B** of the AFM feature-parity effort (transferring capabilities
from the legacy `afm_data_platform` project into the skewnono AFM Metrology page).
Follows Sub-project **A** (Export Layer, complete).

## Background

The legacy `afm_data_platform` shipped an `AdditionalAnalysisImages` component: a tabbed
gallery (Alignment / Tip Condition / Result Analysis) of supplementary images per
measurement, with thumbnails, a full-size dialog, and per-tab bulk download.

Skewnono's AFM page shows only the profile SVG. Its backend contract already models the
other image categories — `align_dir_list`, `tip_dir_list`, `capture_dir_list`,
`tiff_dir_list`, `has_align`, `has_tip` (`back_dev_home/afm/contracts.py:33-43`) — and the
mock populates the **filenames** (`providers/mock.py:394-406`), but:

- No route lists or serves those image bytes; only `get_profile_image_svg` exists.
- The listed filenames (`..._alignment.png`, `..._tip.tiff`, per-site-point `.webp`) have
  no corresponding bytes in the mock.
- `capture_dir_list` is always `["no files"]` in the mock.

## Goals

1. From the measurement detail page, browse **all supplementary image kinds** per
   measurement — mirroring the legacy `image_routes.py`, which serves five directory
   "modes" (`profile`, `tiff`, `align`, `tip`, `capture`). Profile is already shown as its
   own card, so the gallery adds the other four as tabs: **Align** (`align`), **Tip**
   (`tip`), **Capture** (`capture`), **Result** (`tiff`).
2. Open any image full-size and download it individually.
3. Make this fully functional in Phase 1 by generating deterministic placeholder images in
   the mock — populating every one of the four dir-lists (including `capture`, which the
   mock currently leaves empty) so all four tabs display — served through the provider seam
   so Phase 2/3 can swap in real files with no frontend change.

## Non-goals

- **Bulk "Download All" per tab.** Deferred: it fires N separate browser downloads (the
  wart Sub-project A deliberately avoided), and Phase-1 images are placeholders. Per-image
  download only.
- Real image formats in Phase 1. The mock serves `image/svg+xml` placeholders even though
  the contract filenames say `.png`/`.tiff`/`.webp`; `<img>` and download work regardless,
  and the office provider returns true formats later.

## Design

### Backend

**Provider seam** (`back_dev_home/afm/data.py`) — add two functions delegating to
`_provider()`, following the existing pattern (e.g. `get_profile_image_svg`):

- `list_analysis_images(filename: str, image_type: str, tool_name: str | None) -> list[dict]`
  Returns `[{ "name": <image filename>, "url": <serve-route path> }]` for the measurement's
  `{image_type}_dir_list`. Skips the `"no files"` sentinel and unknown types (→ `[]`).
- `get_analysis_image_svg(filename: str, image_type: str, name: str, tool_name: str | None) -> str | None`
  Returns a deterministic seeded placeholder SVG for a valid `(measurement, type, name)`;
  `None` when the measurement is not found, the type is unknown, or the name is not in that
  type's dir-list.

Add both names to `data.py`'s `__all__`.

**Mock provider** (`back_dev_home/afm/providers/mock.py`):

- `IMAGE_TYPE_FIELDS = { "align": "align_dir_list", "tip": "tip_dir_list", "capture": "capture_dir_list", "tiff": "tiff_dir_list" }`
  maps the route's `image_type` to the row's dir-list key.
- **Populate `capture_dir_list`** in the mock row builder (currently hard-coded to
  `["no files"]` at `providers/mock.py:406`): give each measurement a capture image, e.g.
  `[f"{clean_filename}_{sites[0]}_capture.png"]`, so the Capture tab displays at home. Keep
  `align`/`tip` on their existing sparse cadence (realistic — not every measurement has
  them); `tiff` (Result) and `capture` populate broadly.
- `list_analysis_images`: locate the measurement row (`_find_measurement`), read the mapped
  dir-list, drop `"no files"`, and build one entry per name with `url =
  /api/afm/files/<enc filename>/images/<image_type>/<enc name>`.
- `get_analysis_image_svg`: validate the name is in the type's dir-list, then generate a
  placeholder SVG mirroring `get_profile_image_svg` — seeded via
  `_seed_for("analysis-image", tool, filename, f"{image_type}:{name}")` for determinism, a
  per-type accent color (align / tip / capture / tiff distinct), and a text label of
  `tool · lot · image_type · name`.
- Add both to `mock.py`'s `__all__`.

**Office provider** (`back_dev_home/afm/providers/office.py`): add `list_analysis_images`
and `get_analysis_image_svg` as `_not_connected()` stubs, matching the existing pattern.

**Routes** (`back_dev_home/afm/routes.py`) — `image_type` is validated against the four
known types (`align`, `tip`, `capture`, `tiff`); unknown → 404. Import the two new data
functions.

| Route | Returns |
| --- | --- |
| `GET /afm/files/<path:filename>/images/<image_type>?tool=` | `{success, data:[{name,url}], count, tool}` (200; empty list is still 200) |
| `GET /afm/files/<path:filename>/images/<image_type>/<path:name>?tool=` | `image/svg+xml` bytes (404 plaintext if none) |

The two routes differ by path-segment count, so they do not collide with each other or with
the existing point-based `image-file/<point>` route.

### Frontend

**`composables/useAfmDetailApi.ts`** — add:

- `interface AfmAnalysisImage { name: string; url: string }`
- `interface AfmAnalysisImagesResponse { success: boolean; data: AfmAnalysisImage[]; count: number; tool: string }`
- `type AfmImageType = 'align' | 'tip' | 'capture' | 'tiff'`
- `fetchAnalysisImages(toolName: string, filename: string, imageType: AfmImageType): Promise<AfmAnalysisImagesResponse>`
  with in-flight de-dup keyed by `tool|filename|imageType`, mirroring `fetchImage`.
- Export the new function from the composable's returned object.

**`components/afm/detail/AnalysisImages.vue`** (new) — props `{ tool: string; filename: string }`.

- A `UCard` titled "Analysis images" with four tabs (`UTabs`): **Align** (`align`),
  **Tip** (`tip`), **Capture** (`capture`), **Result** (`tiff`).
- Each tab lazy-loads its image list on first activation (fetch once, cache in a
  per-type ref). States: loading (spinner), empty ("No <label> images"), and a thumbnail
  grid (`<img :src="image.url">`, responsive, `overflow` guarded).
- Per-tab count badge on the tab label once loaded.
- Clicking a thumbnail opens a `UModal` lightbox showing the full-size image, its name, and
  a **download** icon-button that fetches the image URL → Blob → downloads
  `{filename}-{imageType}-{name}` (client-guarded; reuses the blob-download pattern
  introduced in Sub-project A's `ProfileImage.vue`).

**Detail page** (`pages/afm/[tool]/[filename].vue`) — render
`<AfmDetailAnalysisImages :tool="toolName" :filename="filename" />` in the right column,
below the existing charts and profile-image card.

## Data flow

```text
pages/afm/[tool]/[filename].vue
  └─ <AfmDetailAnalysisImages :tool :filename>
       ├─ per tab: useAfmDetailApi().fetchAnalysisImages(tool, filename, type)
       │     → GET /afm/files/<filename>/images/<type>  → [{name, url}]
       ├─ thumbnail grid: <img :src="url">
       │     → GET /afm/files/<filename>/images/<type>/<name>  → image/svg+xml
       └─ lightbox download: fetch(url) → Blob → {filename}-{type}-{name}

back_dev_home/afm
  routes.py  → data.list_analysis_images / data.get_analysis_image_svg
             → _provider() → mock (placeholder SVG) | office (_not_connected)
```

## Error handling & edge cases

- Unknown `image_type` → route 404; `list_analysis_images` returns `[]` defensively.
- `"no files"` sentinel → excluded from the list (empty tab, not a broken entry).
- Measurement not found / name not in dir-list → serve route 404.
- Most mock measurements lack `align`/`tip` (only `index % 6 == 0` / `index % 7 == 0`); the
  gallery must render empty tabs gracefully. `tiff` (Result) is common (`index % 4 != 1`) and
  `capture` is populated for every measurement (added by this spec), so those two tabs
  always display at home.
- Lightbox download failure (fetch error) is caught and silently no-ops (best-effort),
  matching `ProfileImage.vue`.

## Testing

Backend — pytest (`.venv/bin/pytest back_dev_home/afm`; pytest 9.1.1 is installed and the
existing `test_contract.py` already runs under it). Route tests use Flask's `test_client`,
mirroring `back_dev_home/chat/tests/test_routes.py`.

- `list_analysis_images`: returns entries for a measurement with `capture`/`tiff` present
  (always populated) and for one with `align`/`tip` present; skips `"no files"`; returns
  `[]` for an unknown type and for a measurement whose dir-list is the sentinel; URLs point
  at the serve route with the right type/name.
- `get_analysis_image_svg`: returns an SVG string (starts with `<svg`) for a valid
  `(measurement, type, name)` across all four types; `None` for unknown type, unknown
  measurement, and a name not in the dir-list; output is deterministic across two calls with
  the same seed inputs.
- `capture` population: every measurement row's `capture_dir_list` is non-sentinel (a
  regression guard on the mock change).
- Routes (`test_client`): list route 200 with `{success, data, count, tool}`; serve route
  200 with `Content-Type: image/svg+xml`; unknown type → 404, missing name → 404.

Frontend: `AnalysisImages.vue` is `.vue` wiring — gated by `npm run typecheck` +
`npm run lint` + in-app verification (load a measurement, confirm all four tabs, thumbnails
on Capture/Result, lightbox, and per-image download).

## Files touched

- `back_dev_home/afm/data.py` (2 seam functions + `__all__`)
- `back_dev_home/afm/providers/mock.py` (2 implementations + type map + `capture_dir_list` population + `__all__`)
- `back_dev_home/afm/providers/office.py` (2 stubs)
- `back_dev_home/afm/routes.py` (2 routes + imports)
- `back_dev_home/afm/tests/` (new backend tests)
- `front-dev-home/app/composables/useAfmDetailApi.ts` (types + `fetchAnalysisImages`)
- `front-dev-home/app/components/afm/detail/AnalysisImages.vue` (new)
- `front-dev-home/app/pages/afm/[tool]/[filename].vue` (render the gallery)

## Follow-on sub-projects (not this spec)

- **C** — chart analytical depth (custom X/Y scatter builder, heatmap outlier/color/sampling
  controls, histogram bin/overlay/stats, points-table column-picker/search/pagination/CSV).
- **D** — nav & UX polish (breadcrumb, See-Together progress+cancel dialog).
