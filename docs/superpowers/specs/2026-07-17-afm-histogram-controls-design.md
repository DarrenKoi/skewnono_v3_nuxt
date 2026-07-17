# AFM Histogram Controls — Design Spec

Date: 2026-07-17
Status: Approved (brainstorming), pending implementation plan
Scope: Sub-project **C3** of the AFM feature-parity effort (part of C; sibling of C2 heatmap
and C4 points-table). Fidelity: **curated** subset of the legacy `HistogramChart.vue`
(783 lines).

## Background

skewnono's `HistogramChart.vue` (114 lines) renders the selected point's profile Z-values
as a fixed 24-bin bar chart with a μ/σ header readout. The legacy histogram adds
bin-count strategies, display modes, a normal-distribution overlay, percentile marklines,
log-scale, and an extended stats box (including prose interpretations of
skewness/kurtosis).

We port a **curated** subset: the analytically useful controls, numeric stats only.

## Goals

Add to the existing Z-value histogram:

1. **Bin method** — `Auto` (Sturges / Freedman-Diaconis; FD when the outlier ratio > 5%) or
   `Custom` (a numeric bin count, clamped 5–200).
2. **Display mode** — `Frequency` / `Density` / `Cumulative`.
3. **Normal-curve overlay** — a toggle (default on) drawing the fitted normal curve scaled
   to the current display mode.
4. **Percentile marklines** — a toggle (default on) marking Q1 / median / Q3.
5. **Extended numeric stats** — header/readout: μ, σ, min, max, Q1, median, Q3, skewness,
   kurtosis, CV%.

## Non-goals

- Prose interpretations of skewness/kurtosis ("moderately skewed") — numbers only.
- Log-scale Y axis (niche for Z-distributions).
- A "Fine" bin preset (redundant between Auto and Custom).
- CSV export of the distribution (Sub-project A already exports the underlying profile).

## Design

### Pure logic — `front-dev-home/app/utils/afmHistogram.ts` (new)

Testable with `node --test` (no DOM/Nuxt imports):

```ts
export type BinMethod = 'auto' | 'custom'
export type HistogramMode = 'frequency' | 'density' | 'cumulative'

export interface HistogramStats {
  count: number
  mean: number
  stdev: number      // population std (÷N)
  min: number
  max: number
  q1: number
  median: number
  q3: number
  skewness: number   // 0 when N < 3 or stdev 0
  kurtosis: number   // EXCESS kurtosis (normal ⇒ 0); 0 when N < 4 or stdev 0
  cv: number         // stdev / |mean| * 100; 0 when mean 0
}

export interface HistogramBins {
  centers: number[]  // bin midpoints
  values: number[]   // per-bin value for the chosen mode
  binWidth: number
  edges: number[]    // length centers.length + 1
}

export interface NormalCurvePoint { x: number, y: number }

// Sturges = ceil(1 + log2(n)); FD = ceil(range / (2·IQR·n^(-1/3))); both clamped [5,200].
// method 'auto' picks FD when the 3σ-outlier ratio > 0.05, else Sturges. 'custom' clamps
// the requested count to [5,200]. Degenerate input (n < 1) → 5.
export const resolveBinCount = (
  zs: number[],
  method: BinMethod,
  customCount: number
): number

// Bin zs into `binCount` equal-width bins over [min, max]. 'frequency' = counts,
// 'density' = counts / (n · binWidth), 'cumulative' = running-sum of counts.
// Empty zs or zero span → single degenerate bin so the chart never throws.
export const computeHistogram = (
  zs: number[],
  binCount: number,
  mode: HistogramMode
): HistogramBins

export const histogramStats = (zs: number[]): HistogramStats

// Fitted normal curve sampled at `steps` points across [min, max], scaled to the mode:
// 'density' = pdf; 'frequency' = pdf · n · binWidth; 'cumulative' = cdf · n.
// Returns [] when stdev is 0. Used for the overlay line series.
export const normalCurvePoints = (
  stats: HistogramStats,
  mode: HistogramMode,
  binWidth: number,
  steps?: number
): NormalCurvePoint[]
```

Internal pure helpers: `quantile(sortedAsc, p)` (linear interp), `mean`, `populationStd`.

Percentiles/quantiles use linear interpolation on the ascending-sorted values, consistent
with `afmHeatmap.ts`.

### Component — `HistogramChart.vue`

- Control row (below header, above chart, shown when `profile.length > 0`): a `USelect`
  for bin method; a `UInput type="number"` for custom bin count (shown only when method is
  `custom`, default 30); a `USelect` for display mode; two `USwitch`/`UCheckbox` toggles for
  the normal overlay and percentile marklines.
- Local refs: `binMethod` (`'auto'`), `customBins` (30), `displayMode` (`'frequency'`),
  `showNormal` (true), `showPercentiles` (true).
- Computed: `zs = profile.map(p => p.z)`; `stats = histogramStats(zs)`;
  `binCount = resolveBinCount(zs, binMethod, customBins)`;
  `hist = computeHistogram(zs, binCount, displayMode)`;
  `normal = showNormal ? normalCurvePoints(stats, displayMode, hist.binWidth) : []`.
- `chartOption`:
  - Bar series over `hist.centers` / `hist.values` (Y-axis label reflects the mode:
    "Frequency" / "Density" / "Cumulative").
  - When `showNormal` and `normal.length`, a second `line` series (smooth, no symbols) on a
    shared value X axis. NOTE: the current bar chart uses a `category` X axis of formatted
    bin centers; to overlay a continuous normal curve, switch the X axis to `type: 'value'`
    and give the bar series `[x, y]` pairs so bars and curve share the numeric axis.
  - When `showPercentiles`, `markLine` on the bar series at `stats.q1`, `stats.median`,
    `stats.q3` (vertical `xAxis` marklines) labeled Q1 / Med / Q3.
- Header/readout: μ, σ (existing) extended with a compact stats line — min, max, Q1,
  median, Q3, skewness, kurtosis, CV% (2-dp, tabular nums). Keep it to one wrapped row to
  avoid crowding the small card.
- `useEchart(chartEl, chartOption, { exportName: props.exportName })` unchanged (PNG export
  preserved).

## Error handling & edge cases

- Empty profile → existing "No distribution data" state; utils return zeroed stats / a
  single degenerate bin / empty normal curve.
- Zero spread (all-equal Z) → `computeHistogram` yields one bin; `normalCurvePoints` returns
  `[]` (stdev 0); no divide-by-zero.
- `N < 3` → skewness 0; `N < 4` → kurtosis 0; `mean === 0` → CV 0.
- Custom bin count out of range → clamped to [5, 200]; non-finite → treated as the clamp
  floor (5).

## Testing

`node --test` unit tests for `afmHistogram.ts`:

- `resolveBinCount`: Sturges for well-behaved data, FD when outlier-heavy, custom clamps to
  [5,200], degenerate → 5.
- `computeHistogram`: bin counts sum to N (frequency); density integrates to ≈1
  (Σ value·binWidth ≈ 1); cumulative is monotonic non-decreasing ending at N; single-bin
  degenerate case for zero span.
- `histogramStats`: known mean/std/quantiles; skewness sign on a skewed set; excess
  kurtosis ≈ 0 for a symmetric plateau vs. positive for a peaked set; CV; N<3/N<4/mean-0
  guards.
- `normalCurvePoints`: empty when stdev 0; peak near the mean; length == steps otherwise.

Component is `.vue` wiring — gated by `npm run typecheck` + `npm run lint` + in-app
verification (toggle bin method/mode/overlays on a real profile; confirm the curve overlays
the bars and marklines land at the quartiles; default view still reads as a sensible
histogram).

## Files touched

- `front-dev-home/app/utils/afmHistogram.ts` (new)
- `front-dev-home/app/utils/afmHistogram.test.ts` (new)
- `front-dev-home/app/components/afm/detail/HistogramChart.vue` (controls + wiring)

## Follow-on (not this spec)

- **C4** — points-table upgrades (column-picker, search, pagination, summary tiles, CSV),
  curated.
