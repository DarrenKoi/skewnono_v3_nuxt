# AFM Export Layer — Design Spec

Date: 2026-07-17
Status: Approved (brainstorming), pending implementation plan
Scope: Sub-project **A** of the AFM feature-parity effort (transferring capabilities
from the legacy `afm_data_platform` project into the skewnono AFM Metrology page).

## Background

The legacy `afm_data_platform` (Vue 3 + Vuetify) shipped a data/image **export layer**
that skewnono's AFM page never picked up:

- A "Download Data" menu on the measurement detail view exporting Measurement Info,
  Summary Statistics, Detailed point data, Profile (X,Y,Z), and "Download All (CSV)".
- A per-point raw-image download button.
- Per-chart PNG export buttons.

Skewnono already owns most of the underlying machinery, so this sub-project is
primarily **wiring the AFM detail page into existing utilities**, not building export
infrastructure:

- `utils/csvDownload.ts` — `downloadCsv(filename, headers, rows)` and `escapeCsvValue`,
  with the UTF-8 BOM + CRLF Excel/Korean-mojibake fix already baked in.
- `composables/useEchart.ts` — every chart already mounts a hover-reveal PNG download
  button (`downloadChartImage`, opt-out via `disableDownload`). It falls back to a
  generic filename because callers pass no `exportName`.

## Goals

1. From the measurement detail page, export the loaded measurement's data as CSV —
   individually per dataset and as one combined file.
2. Download the selected point's profile image.
3. Give the already-working chart PNG downloads meaningful filenames.

## Non-goals

- Raw TIFF/WebP instrument-image download. Skewnono serves an SVG profile image, not
  raw instrument frames; align/tip/capture/tiff images belong to **Sub-project B**
  (additional-image gallery).
- Any new export button on charts. The hover PNG button already exists; only its
  filename changes.
- Server-side export/zipping. Everything is client-side from data already fetched.

## Design

### 1. CSV export

**New composable `composables/useAfmExport.ts`** — pure CSV builders over the loaded
`AfmDetailPayload` plus the currently-selected point's profile points. Each builder
returns `{ headers: string[], rows: unknown[][] }` (or `null`/empty when the dataset is
absent) so callers can both download and read a count.

| Builder | Source | Columns |
| --- | --- | --- |
| `buildInfoCsv(info)` | `payload.information` | `key,value` (one row per entry) |
| `buildSummaryCsv(summary)` | `payload.summary` (`AfmSummaryRow[]`) | `Site, ITEM`, then every dynamic measurement key in first-row order |
| `buildDetailedCsv(data)` | `payload.data` (`AfmDetailRow[]`) | union of keys in stable first-row-then-appended order |
| `buildProfileCsv(points)` | selected-point `AfmProfilePoint[]` | `x,y,z` |

**Combined export** `buildCombinedCsv(...)` concatenates the four datasets into a single
CSV string, each preceded by a `## <Section>` label line and separated by a blank line:

```text
## Measurement Info
"key","value"
...

## Summary (by site)
"Site","ITEM","<col1>",...
...

## Detailed Points
...

## Profile (selected point <n>)
"x","y","z"
...
```

Sections with no data render the header line `## <Section> (no data)` and no rows, so the
combined file is always well-formed.

**Download primitive.** `downloadCsv()` only emits a single header+rows table and cannot
express the combined multi-section file. Refactor `utils/csvDownload.ts`:

- Extract `downloadCsvRaw(filename: string, content: string): void` owning the
  BOM (`﻿`) prefix, CRLF joining is done by the caller/section builder, blob
  creation, and anchor click. It prepends the BOM to whatever content string it is given.
- Reimplement the existing `downloadCsv(filename, headers, rows)` to build its CRLF-joined
  content and delegate to `downloadCsvRaw`. Public signature and behaviour of
  `downloadCsv` are unchanged; existing callers and tests stay green.
- `useAfmExport` builds each section's CSV text with `escapeCsvValue` + CRLF joins and
  calls `downloadCsvRaw` for the combined file; individual exports call the existing
  `downloadCsv`.

**UI — export menu.** Add a NuxtUI `UDropdownMenu` labelled **"내보내기"** (download icon)
to the detail-page header in `pages/afm/[tool]/[filename].vue`, beside the existing
"Back to search" control. Items, each showing a live count and disabled when the count
is 0 (or, for Profile, when no point is selected/loaded):

- **Download All (CSV)** → `buildCombinedCsv`
- divider
- **Measurement Info** (`n` fields)
- **Summary** (`n` sites)
- **Detailed Points** (`n` points)
- **Profile — selected point** (`n` points)

**Filenames.** `{filename}-info.csv`, `-summary.csv`, `-detailed.csv`,
`-profile-point{n}.csv`, and `{filename}-all.csv`, where `{filename}` is the measurement
filename from the route/detail.

### 2. Profile image download

Add a small download icon-button to `components/afm/detail/ProfileImage.vue`, near the
"Point N" badge. It downloads the currently-displayed profile SVG for the selected point
as `{filename}-point{n}.svg`. The image endpoint/URL already exists in
`useAfmDetailApi`; the button fetches those SVG bytes into a Blob and triggers a download
(client-guarded). Hidden/disabled when no image is loaded for the point.

### 3. Chart PNG filenames

Thread the measurement `filename` (and tool for the trend chart) into the four AFM chart
components as a prop, and pass `exportName` to their existing `useEchart(...)` calls:

| Component | `exportName` |
| --- | --- |
| `detail/HeatmapChart.vue` | `{filename}-heatmap` |
| `detail/HistogramChart.vue` | `{filename}-histogram` |
| `detail/SummaryScatterChart.vue` | `{filename}-summary-scatter` |
| `trend/TimeSeriesChart.vue` | `{tool}-trend` |

No other chart change; the hover download button and its date-stamped
`chartExportFilename` logic are untouched.

## Data flow

```text
pages/afm/[tool]/[filename].vue
  ├─ useAfmDetail → AfmDetailPayload (information, summary, data, available_points)
  ├─ selected point → useAfmProfile → AfmProfilePoint[]  (already wired)
  │
  ├─ useAfmExport(payload, selectedPoint, profilePoints)
  │     buildInfoCsv / buildSummaryCsv / buildDetailedCsv / buildProfileCsv / buildCombinedCsv
  │     → downloadCsv / downloadCsvRaw (utils/csvDownload.ts)
  │
  ├─ UDropdownMenu "내보내기"  → calls the export fns; counts drive labels + disabled
  ├─ ProfileImage.vue          → SVG blob download
  └─ Heatmap/Histogram/SummaryScatter/(TimeSeries) → exportName prop → useEchart
```

## Error handling & edge cases

- Empty dataset → builder returns empty; menu item shows count 0 and is disabled; no file
  is written (existing `downloadCsv` already no-ops on `rows.length === 0`).
- No point selected or profile not yet loaded → Profile CSV item and image-download button
  disabled; combined CSV emits the `## Profile (no data)` section.
- All download paths are `import.meta.client`-guarded (inherited from `csvDownload.ts`).
- Dynamic summary/detailed columns: column order is taken from the first row, then any
  keys appearing only in later rows are appended, so ragged rows never drop columns.

## Testing

Vitest unit tests (pure functions only; no DOM download simulation):

- `useAfmExport` builders: section headers/columns for Info, Summary (dynamic columns),
  Detailed (ragged-row column union), Profile; empty-dataset handling; `buildCombinedCsv`
  section labels and `(no data)` fallback; quote-escaping via `escapeCsvValue`.
- `csvDownload`: a regression test that `downloadCsv` output is unchanged after the
  `downloadCsvRaw` extraction (assert the composed content string the primitive receives,
  or keep the existing test suite passing).

## Files touched

- `front-dev-home/app/composables/useAfmExport.ts` (new)
- `front-dev-home/app/utils/csvDownload.ts` (add `downloadCsvRaw`, refactor `downloadCsv`)
- `front-dev-home/app/pages/afm/[tool]/[filename].vue` (export menu)
- `front-dev-home/app/components/afm/detail/ProfileImage.vue` (image download button)
- `front-dev-home/app/components/afm/detail/HeatmapChart.vue` (exportName prop)
- `front-dev-home/app/components/afm/detail/HistogramChart.vue` (exportName prop)
- `front-dev-home/app/components/afm/detail/SummaryScatterChart.vue` (exportName prop)
- `front-dev-home/app/components/afm/trend/TimeSeriesChart.vue` (exportName prop)
- Tests under the project's frontend test location (mirror existing `csvDownload` tests).

## Follow-on sub-projects (not this spec)

- **B** — additional-image gallery (align/tip/capture/tiff): backend image-list route + UI.
- **C** — chart analytical depth (custom X/Y scatter builder, heatmap outlier/color/sampling
  controls, histogram bin/overlay/stats, points-table column-picker/search/pagination/CSV).
- **D** — nav & UX polish (breadcrumb, See-Together progress+cancel dialog).
