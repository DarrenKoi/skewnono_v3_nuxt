# AFM Heatmap Controls — Design Spec

Date: 2026-07-17
Status: Approved (brainstorming), pending implementation plan
Scope: Sub-project **C2** of the AFM feature-parity effort. Part of Sub-project **C**
(chart analytical depth); siblings C3 (histogram) and C4 (points-table) follow.
Fidelity: **curated** high-value subset of the legacy `HeatmapChart.vue` (628 lines).

## Background

skewnono's `HeatmapChart.vue` (106 lines) renders the selected measurement point's profile
as a wafer scatter colored by Z via an ECharts `visualMap` (fixed blue→green→amber→red
ramp), with a tooltip and a point count. The legacy `afm_data_platform` heatmap adds
outlier removal (5 methods), 8 color schemes, sampling for >50k points, click-to-select,
a stats chip row, and a CSV export.

We port a **curated** subset. Two legacy features are intentionally excluded because
skewnono already covers them elsewhere: CSV export (Sub-project A's profile export) and
click-to-select-a-point (meaningless — this heatmap already shows a single selected point's
profile). Sampling is deferred (mock profiles are ~400 points; the real need is unproven).

## Goals

Add three curated controls to the existing heatmap:

1. **Outlier removal** — `None` (default) / `IQR` / `Z-Score`, filtering Z-values before
   rendering, with a numeric threshold (default 1.5 for IQR, 3 for Z-Score).
2. **Color scheme** — `Spectral` (current ramp, default) / `Viridis` / `Grayscale`.
3. **Stats readout** — min / max / mean Z in the header, plus "N removed" when a filter is
   active.

## Non-goals

- Sampling for large point counts (deferred until real office data needs it).
- Heatmap CSV export (Sub-project A already exports profile X/Y/Z).
- Click-to-select a point (not meaningful for a single-point profile heatmap).
- Percentile / "Auto-smart" outlier methods (redundant — legacy's Auto is IQR internally).

## Design

### Pure logic — `front-dev-home/app/utils/afmHeatmap.ts` (new)

Testable with `node --test` (no DOM/Nuxt imports; `import type` for `AfmProfilePoint`):

```ts
export type OutlierMethod = 'none' | 'iqr' | 'zscore'
export type HeatmapColorScheme = 'spectral' | 'viridis' | 'grayscale'

export const OUTLIER_DEFAULT_THRESHOLD: Record<OutlierMethod, number>
  // { none: 0, iqr: 1.5, zscore: 3 }

export interface HeatmapFilterResult {
  kept: AfmProfilePoint[]
  removed: number
}

// Filter points whose z falls outside the method's bounds. 'none' → all kept, 0 removed.
// IQR: [q1 - k*iqr, q3 + k*iqr]; Z-Score: [mean - k*std, mean + k*std] (k = threshold).
// Fewer than 4 points, or a non-finite/degenerate threshold, or std === 0 → all kept.
export const filterProfileByOutlier = (
  points: AfmProfilePoint[],
  method: OutlierMethod,
  threshold: number
): HeatmapFilterResult

export interface HeatmapStats {
  count: number
  min: number
  max: number
  mean: number
}

// Z stats over the given points; count 0 → { count: 0, min: 0, max: 0, mean: 0 }.
export const heatmapStats = (points: AfmProfilePoint[]): HeatmapStats

// visualMap inRange color arrays per scheme. 'spectral' is the CURRENT ramp
// (['#3b82f6','#10b981','#f59e0b','#ef4444']) so the default look is unchanged.
export const HEATMAP_COLOR_RAMPS: Record<HeatmapColorScheme, string[]>
```

Internal pure helpers: `quantile(sortedAsc, p)`, `mean(nums)`, `stdev(nums, mean)`.

### Component — `HeatmapChart.vue`

- Add a compact control row (below the header, above the chart): a `USelect` for outlier
  method, a `UInput type="number"` for the threshold (shown only when method ≠ `none`), and
  a `USelect` for color scheme. Use `size="xs"` NuxtUI controls to stay compact.
- Local refs: `outlierMethod` (`'none'`), `threshold` (init 1.5), `colorScheme`
  (`'spectral'`). When `outlierMethod` changes, reset `threshold` to
  `OUTLIER_DEFAULT_THRESHOLD[method]`.
- `filtered = computed(() => filterProfileByOutlier(props.profile, outlierMethod, threshold))`.
- `stats = computed(() => heatmapStats(filtered.value.kept))`.
- `chartOption` uses `filtered.value.kept` for the series data, `zRange` from
  `stats` (min/max), and `inRange.color = HEATMAP_COLOR_RAMPS[colorScheme]`.
- Header stats: replace/extend the "N points" span with min / max / mean (2-dp, tabular
  nums) and, when `outlierMethod !== 'none'`, a "N removed" chip.
- The existing `useEchart(chartEl, chartOption, { exportName })` call and tooltip are
  unchanged (the hover PNG export keeps working).

## Error handling & edge cases

- Empty profile → existing "Heat map data unavailable" state (unchanged); util returns
  zeroed stats / empty kept.
- Degenerate data (all-equal Z, std 0, <4 points) → outlier filter is a no-op (all kept),
  so the chart never blanks from over-aggressive filtering.
- Non-finite/blank threshold input → treated as the method default (no filtering surprise).
- Switching color scheme never refilters; switching method/threshold refilters via the
  computed.

## Testing

`node --test` unit tests for `afmHeatmap.ts` (pure):

- `filterProfileByOutlier`: IQR removes a planted extreme and reports `removed`; Z-Score
  likewise; `none` keeps all; <4 points keeps all; all-equal Z (std 0) keeps all;
  non-finite threshold keeps all.
- `heatmapStats`: min/max/mean over a known set; empty → zeros.
- `HEATMAP_COLOR_RAMPS`: `spectral` equals the current ramp exactly (guard against a
  default-look regression); every scheme is a non-empty string array.

Component is `.vue` wiring — gated by `npm run typecheck` + `npm run lint` + in-app
verification (toggle methods/schemes on a real profile, confirm the chart refilters and the
stats/removed readout updates).

## Files touched

- `front-dev-home/app/utils/afmHeatmap.ts` (new)
- `front-dev-home/app/utils/afmHeatmap.test.ts` (new)
- `front-dev-home/app/components/afm/detail/HeatmapChart.vue` (controls + wiring)

## Follow-on (not this spec)

- **C3** — richer histogram (bin methods, display modes, distribution overlay, extended
  stats), curated.
- **C4** — points-table upgrades (column-picker, search, pagination, summary tiles, CSV),
  curated.
