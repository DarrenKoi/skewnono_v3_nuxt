# Spec — FDC sparkline matrix for the single-MSR sequence workbench

Date: 2026-07-25
Scope: Skewvoir TimeSeries view, `single` scope only. Adds a small-multiples overview
above the existing per-param panels in `SequenceWorkbench.vue`. The `set` scope
(multi-MSR comparison) is explicitly out of scope; see "Deferred" below.

## Problem

A single MSR carries one CD parameter plus N per-sequence dynamic FDC params — 10 in
the Phase-1 mock (`back_dev_home/msr_file/providers/mock.py:314-325`), and an unknown
larger N at the office, because `office_example.py:307` treats `DYNAMIC_FDC_SPECS` as
a *baseline catalog* rather than a closed set.

Both existing timeseries surfaces compensate for that N in a lossy way:

- `SequenceWorkbench.vue:75-99` renders **one full-height panel per param**. With 10
  dynamic params that is ~11 stacked panels — you cannot see CD and a suspect FDC
  channel in the same viewport, which is precisely the comparison the page exists to
  support.
- `FdcTimeSeriesChart.vue:29-34` takes the opposite trade: it collapses every param
  onto **one shared σ-drift axis** because Brightness (≈128 DN) and StigmaX (≈0 %)
  cannot share a linear axis. That makes params comparable but discards native units.

Neither lets an engineer answer the actual question: *which tool parameter moved with
my CD, on this run?*

## Approach

Use the ECharts 6 `matrix` coordinate system, as in the upstream
`matrix-sparkline` example (`since: 6.0.0`).

The mechanism is worth stating precisely, because the example's name is misleading:
**there is no sparkline series type.** The example builds an ordinary cartesian
`grid` + `xAxis` + `yAxis` + `line` series *per cell*, and positions each grid with
`coordinateSystem: 'matrix', coord: [xVal, yVal]`. The `matrix` component contributes
layout, row/column headers, corner labels, and cell merging — nothing else.

Three properties make this the right fit:

| Property | Why it matters here |
| --- | --- |
| Each cell keeps its own `yAxis` with `scale: true` | Native units survive. The σ-normalization forced on `FdcTimeSeriesChart` is unnecessary. |
| `dataZoom: { xAxisIndex: 'all' }` | One brush over the sequence range reframes every param at once. |
| `matrix.y.data` renders a row-header column | FDC category grouping comes free instead of being hand-drawn. |

Verified before committing to this: `GridOption extends ComponentOption`, and
`ComponentOption` declares `coordinateSystem?: string` and `coord?:
CoordinateSystemDataCoord` (`node_modules/echarts/types/dist/echarts.d.ts:8222-8232`).
The option type-checks under the repo's `vue-tsc` run with no cast or module
augmentation. `useEchart.ts:1` imports the full `echarts` bundle, so `matrix` needs no
component registration.

Rejected alternatives: hand-laid multi-grid small multiples (the `FdcPanel.vue:303-328`
pattern) — same picture, but row headers, cell merging and layout math all become ours
for a variable N; and a CSS grid of N independent chart instances — smallest diff, but N
`ResizeObserver`s and no shared zoom or cursor without new `echarts.connect` plumbing.

## Layout model

Rows are FDC categories; columns are params within a category. `columns` is computed
from the widest row — including the suspects row — and never hardcoded, because N is
not ours to assume.

| Row | Contents |
| --- | --- |
| 0 | `CD` — the active CD parameter, spanning the full matrix width |
| 1 | `주요 용의자` — the `min(4, evaluable)` highest-\|r\| params, **duplicated** from below, never moved |
| 2+ | one row per category present; cells ordered by \|r\| descending within the row |

"Evaluable" means `readiness === 'ready'`; see "Honesty constraints". Ties in |r| break
by param name so the order is stable across renders.

Ranking and category grouping pull against each other: a global sort by |r| would
scramble the category rows, since the strongest suspects come from different
categories. Duplicating them into a fixed row resolves that without destroying either
structure — the categories below stay complete and in their normal order.

Cell anatomy at ~150x72 px: param name, `r` badge, sparkline, unit, and a single
`yAxis` max label (`interval: Number.MAX_SAFE_INTEGER` with `showMaxLabel: true`, the
example's trick for one label in a tiny cell).

## Modules

### `app/utils/skewvoirAnalysis/paramMatrix.ts` (new, pure)

```text
buildParamMatrix(model, rows, dynamicFdc, fdcParams, cdParam) -> ParamMatrixModel
```

Owns all judgement: correlating each FDC param against CD, resolving Korean row
labels, ordering cells within a row, selecting suspects, computing column count.
Returns a flat `{ columns, rows: MatrixRow[], sequences, demoCoupled }`. Knows nothing
about ECharts or Vue.

`analyzeSequence()` already supplies most of the input: `FdcSeqSeries`
(`sequence.ts:61-68`) carries `param`, `category`, `unit`, `nominal`, `points`,
`stats`, and `SequenceModel` carries `sequences` and `siteBySequence`. The only
genuinely new computation is the per-param correlation to CD, which
`buildCdFdcRelationship` (`relationships.ts:171-205`) already provides.

`FdcSeqSeries` carries `category` (the code) but not `category_label` (the Korean row
header, which lives on `FdcParamSummary`). Resolve the label here by lookup against
`fdc_params` rather than widening `FdcSeqSeries` — that keeps `sequence.ts` and its
existing test file untouched.

### `app/components/ebeam/skewvoir/timeseries/ParamMatrix.vue` (new, presentational)

Props `model: ParamMatrixModel` and `focused: number | null`; emits `select(sequence)`
and `drill(param)`. Builds the ECharts option and nothing else. It takes the **model,
not the `analysis` object**, so it stays reusable for the `set` scope later without
dragging the composable along.

### `app/composables/useEchart.ts` (changed, additive)

Widen `onGridClick` from `(xValue: number)` to `(xValue: number, gridIndex: number)`.

The existing implementation (`useEchart.ts:89-107`) already iterates every grid, uses
`chart.containPixel({ gridIndex }, point)` to find the one the click landed in, and
converts back to axis space — it just discards which grid it was. Every current caller
(`FdcSequenceTrend.vue:117`, others) ignores a second argument, so this breaks nothing.

### `app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue` (changed)

Mount the matrix above the CD pane; keep all existing panels. Add one `computed`
calling `buildParamMatrix` with the `SequenceModel` it already builds. Handle `drill`
by scrolling the matching panel into view.

## Interaction

Clicking a cell does both jobs in one gesture: it sets the shared cursor to the clicked
sequence — what every other pane's click already does, via
`analysis.setFocusedSequence` plus `setFocusedSite` — **and** scrolls that param's
detail panel into view with `block: 'nearest'`, a no-op when the panel is already
visible. No second gesture is invented.

- `dataZoom: [{ type: 'inside', xAxisIndex: 'all' }, { type: 'slider', xAxisIndex: 'all' }]`
- `axisPointer: { link: [{ xAxisIndex: 'all' }] }` for a hover crosshair across cells,
  the same wiring as `FdcPanel.vue:308`
- The persisted focus renders as a vertical `markLine` per cell, so the selected
  sequence stays visible in every cell while the pointer is elsewhere

## Honesty constraints

`relationships.ts:203` hardcodes `demoCoupled: true` for every CD↔FDC join. On Phase-1
data both CD drift and FDC drift derive from one per-MSR `health` scalar
(`mock.py:637-646`), so every correlation is a manufactured artifact. A confident
ranked suspect list built on that would be fiction.

- The suspects row header reuses the **existing** chip from
  `SequenceWorkbench.vue:84-86` — 「데모 데이터 · 방법 검증 불가」. Do not invent new
  wording.
- Cells with `readiness === 'unavailable'` show `평가 불가`, never a number, and are
  excluded from the suspects row. `assess()` (`relationships.ts:79-90`) already
  distinguishes *no pairs* / *n<3* / *constant axis*; that `reason` goes in the tooltip.
- When no param is evaluable, omit the suspects row entirely rather than render it
  empty.

## Failure and empty states

- `hasFdc === false` → CD row only, plus the existing `fdcReason` text. Never an empty
  matrix.
- Pending and error states need nothing new: the matrix mounts inside the workbench's
  existing `v-else` branch (`SequenceWorkbench.vue:36`) and inherits those guards.
- Missing per-sequence values render as gaps (`connectNulls: false`), matching
  `FdcSequenceTrend.vue:93` and `WaferMap.vue:237`. Only the multi-MSR trend connects
  across gaps.

## Testing

`app/utils/skewvoirAnalysis/paramMatrix.test.ts`, run by `node --test` per the repo's
72 existing util tests:

- row grouping and Korean label resolution from `fdc_params`
- within-row ordering by |r| descending, with name as a stable tie-break
- suspects row caps at 4 and excludes unevaluable params
- suspects row omitted when nothing is evaluable
- column count equals the widest row
- CD row present even when `hasFdc` is false

The component gets no unit test. The repo has zero component tests; this change does
not start that convention. Verify it visually through the `/verify` skill.

## Verification item before implementation

The CD row spans the full matrix width. `MatrixCoordRangeOption`
(`echarts.d.ts:10390-10400`) documents range coords such as `[[2, 5], 8]`, and `grid`
inherits `coord` from `ComponentOption` — but the upstream example only ever places
grids at single cells, so **grid spanning is unverified**. Make this the first task: a
short spike against the real API.

Fallback if grid range coords are unsupported: render the CD row as a plain
non-matrix grid pinned above the matrix. The shared `dataZoom: { xAxisIndex: 'all' }`
covers it either way, so the interaction model is unaffected.

## Deferred

- **`set` scope matrix** (rows = param, columns = MSR) — the natural second use of the
  same component, once the single-MSR version proves out. `ParamMatrix.vue` takes a
  model rather than the analysis object specifically to keep that door open.
- **Replacing the stacked panels.** The matrix is an overview layer; the panels keep
  the detailed reading (per-pane stats meta: start/end/range/slope/결측).
