# Chart image download + TAT-tab chart color distinction — Design

- Date: 2026-07-16
- Status: Approved (design)
- Area: `front-dev-home` (Nuxt 4 SPA), ECharts charts

## Problem

1. On `recipe-status?tab=tat`, the two charts — **Top recipe by TAT** (horizontal
   bar) and **Daily TAT trend** (line) — share the same layout but also inherit
   the *same* first theme-palette color, so they read as visually identical. They
   should keep an identical layout (height, padding, grid) but be distinguishable
   by color.
2. No chart in the project can be exported as an image today. Only tabular data
   has CSV/clipboard export. Users want to download any chart as an image, and
   this should apply to **all** charts, not just the TAT tab.

## Current architecture (as-found)

- Every chart in the project (26 chart-rendering files) is instantiated through a
  single shared composable: `app/composables/useEchart.ts`, which does a raw
  `echarts.init(el, theme)` on a plain `<div ref>`. There is **no** `<VChart>`
  and **no** `BaseChart.vue`.
- `useEchart(elRef, optionRef, options?)` centrally manages lifecycle: init on
  mount, re-init on container remount, `setOption(next, true)` on option change,
  dispose + re-init on theme change, window `resize`, dispose on unmount.
- Theming: `app/composables/useEchartsTheme.ts` exposes `resolvedThemeName` and
  `palette`; `app/utils/echartsThemes.ts` registers 6 themes and renders charts on
  a **transparent** canvas so they inherit the card surface. Individual chart
  options generally do **not** hardcode series colors.
- Table export utilities live in `app/utils/csvDownload.ts` (`downloadCsv`,
  `copyTableToClipboard`) — the temporary-`<a>` download pattern is reused here.
- The two TAT charts live in `app/components/ebeam/RecipeTatView.vue`:
  bar `barOption` (≈ lines 590–634), trend `trendOption` (≈ lines 455–494), both
  rendered into `h-[400px] w-full` divs via `useEchart`.

Because all charts funnel through `useEchart`, image-download is added in **one
place** and reaches every chart.

## Part A — Universal chart image download

Single file changed: `app/composables/useEchart.ts`.

### Behavior

- After `echarts.init`, the composable makes the host `<div>` a positioning
  context (`position: relative` if currently static) and adds the class
  `sk-chart-host`, then appends a `<button class="sk-chart-dl-btn">` (download
  glyph, top-right corner) as an overlay child.
- A **singleton `<style>`** element is injected into `<head>` exactly once
  (guarded by an id) with the button styling and hover/focus reveal:
  - `.sk-chart-dl-btn` is `opacity: 0` by default.
  - `.sk-chart-host:hover .sk-chart-dl-btn` and
    `.sk-chart-dl-btn:focus-visible` set `opacity: 1`.
  - Button is keyboard-focusable and has an `aria-label`/`title` of
    "Download chart image".
- On click:
  - `const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor })`.
  - `backgroundColor` is resolved from the active theme via `useEchartsTheme`
    (card surface color) so the PNG is **not** transparent and matches light/dark.
  - Trigger a download with a temporary `<a download=…>` (same approach as
    `csvDownload.ts`), then revoke.
- **Filename:** resolved by a pure helper `chartExportFilename(name, titleText,
  date)`:
  - use `exportName` option if provided, else `option.title.text` if present,
    else `"chart"`;
  - slugify (lowercase, non-alphanumerics → `-`, collapse repeats, trim);
  - append `-YYYY-MM-DD` and `.png`.
- **New optional signature:**
  `useEchart(elRef, optionRef, { onClick?, exportName?, disableDownload? })`.
  - `exportName?: string` — preferred filename base.
  - `disableDownload?: boolean` — escape hatch for charts where an overlay would
    collide with the chart's own controls (e.g. `skewvoir/WaferMap.vue`). Default
    `false`, so all charts get the button unless explicitly opted out.
- **Lifecycle:** the button element, its event listener, and any host-class/style
  mutation are torn down together with the chart on dispose and on the
  theme-change / container-remount re-init paths, so there are no duplicate
  buttons or leaked listeners. The singleton `<style>` is left in place (cheap,
  shared).

### Notes / edge cases

- The overlay button is a DOM sibling of ECharts' own canvas inside the host div;
  it does not intercept chart interactions except within its own small hit area
  (top-right corner). Acceptable trade-off for the auto-inject approach.
- `getDataURL` renders from the live chart, so exported image reflects the current
  option/zoom/theme state.

## Part B — TAT-tab chart color distinction

Single file changed: `app/components/ebeam/RecipeTatView.vue`.

- Keep both charts **layout-identical**. Both are already `h-[400px]`; align their
  `grid` insets so the bar and trend share consistent padding/margins.
- **Color distinction**, read from `useEchartsTheme().palette` (theme-aware across
  all 6 themes):
  - Bar (`barOption`): `series[0].itemStyle.color = palette[0]`.
  - Trend (`trendOption`): `series[0].lineStyle.color = palette[1]` and the
    `areaStyle` tint derived from `palette[1]`.
- Pass `exportName` to the two `useEchart` calls:
  - bar → `exportName: 'top-recipe-by-tat'`
  - trend → `exportName: 'daily-tat-trend'`

## Testing

- **Unit (Vitest):** `chartExportFilename(name, titleText, date)` — cases:
  explicit name wins; falls back to title text; falls back to `"chart"`;
  slugifies spaces/symbols/casing; appends the date and `.png`.
- **Manual verify** (`/skill verify` flow):
  - `recipe-status?tab=tat`: the two charts are visually distinct by color, layout
    unchanged; hover reveals the download button on both; downloaded PNG has a
    solid (non-transparent) background and a meaningful filename.
  - Spot-check auto-coverage on 2–3 unrelated charts (e.g. a skewvoir line chart,
    an AFM heatmap) — button appears and downloads work with no per-component
    change.

## Scope guard (YAGNI)

- PNG only. No SVG export, no chart-as-CSV, no per-chart format menu, no bulk
  "download all charts". A single hover-reveal button per chart.
- No new dependency; reuse existing ECharts `getDataURL`, `useEchartsTheme`, and
  the `csvDownload.ts` download idiom.

## Files touched

- `app/composables/useEchart.ts` — download overlay + `exportName`/`disableDownload`
  options; imports the `chartExportFilename` helper from `app/utils/chartExport.ts`.
- `app/components/ebeam/RecipeTatView.vue` — series colors + `exportName` args +
  grid alignment.
- `app/utils/chartExport.ts` (new) + `chartExport.test.ts` (new) — pure filename
  helper and its spec.
