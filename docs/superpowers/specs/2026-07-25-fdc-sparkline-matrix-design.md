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

Rows are FDC categories; columns are params within a category.

`columns` is the widest row, and `MAX_COLUMNS = 4` bounds it *structurally*: categories
wrap at `MAX_COLUMNS` and the evidence row is sliced by it, so no row can exceed the cap
and no clamp is needed at the end. The cap is load-bearing,
not cosmetic: rows are categories, so their count is small and fixed, and letting
`columns` track the widest row means a single fat category dictates cell width for the
*entire* matrix. If the office catalog puts 15 params in `stage_drift`, an uncapped
matrix becomes 15 columns wide and every cell shrinks to roughly 60 px — illegible,
which defeats the point. A category with more than `MAX_COLUMNS` params **wraps onto
continuation rows** (row header repeated with a continuation marker) instead of widening
the matrix. Cell size therefore stays bounded for any N the office adapter returns.

| Row | Contents |
| --- | --- |
| 0 | `CD` — the active CD parameter, spanning the full matrix width |
| 1 | `주요 검토 근거` — the `min(MAX_EVIDENCE, MAX_COLUMNS, evaluable)` highest-\|r\| params, **duplicated** from below, never moved |
| 2+ | one row per category present; cells ordered by \|r\| descending within the row |

"Evaluable" means the cell's `rState === 'value'`; see "Honesty constraints". Ties in
|r| break by param name so the order is stable across renders.

Ranking and category grouping pull against each other: a global sort by |r| would
scramble the category rows, since the strongest evidence comes from different
categories. Duplicating them into a fixed row resolves that without destroying either
structure — the categories below stay complete and in their normal order.

Cell anatomy at ~150x72 px: param name, `r` badge, sparkline, unit, and a single
`yAxis` max label (`interval: Number.MAX_SAFE_INTEGER` with `showMaxLabel: true`, the
example's trick for one label in a tiny cell).

## Modules

### `app/utils/skewvoirAnalysis/paramMatrix.ts` (new, pure)

```text
buildParamMatrix(model, source) -> ParamMatrixModel
```

Owns all judgement: correlating each FDC param against CD, resolving Korean row
labels, ordering cells within a row, selecting the lead evidence, computing column
count. `source` is the same `SequenceSource` fed to `analyzeSequence`, and the CD
parameter is read from `model.parameter` — passing either twice would let the CD
reference disagree with itself.
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

Props `model: ParamMatrixModel` and `colors: Record<string, string>`; emits `select(sequence)`
and `drill(param)`. Builds the ECharts option and nothing else. It takes the **model,
not the `analysis` object**, so it stays reusable for the `set` scope later without
dragging the composable along.

### `app/composables/useEchart.ts` (changed, additive)

Widen `onGridClick` from `(xValue: number)` to `(xValue: number, gridIndex: number)`.

The existing implementation (`useEchart.ts:89-107`) already iterates every grid, uses
`chart.containPixel({ gridIndex }, point)` to find the one the click landed in, and
converts back to axis space — it just discards which grid it was.

`onGridClick` has exactly **one** caller in the whole app: `ScePanel.vue:627`
(`onGridClick: x => setCoeffIndex(x)`). It passes a unary arrow function, and JavaScript
ignores extra arguments, so the widening breaks nothing. (An earlier draft of this spec
cited `FdcSequenceTrend.vue:117` as a caller; that line supplies `onClick`, not
`onGridClick`.)

Matrix placement does not disturb that hit-testing, which was the main risk to this
mechanism. `containPixel` resolves the finder to `gridModel.coordinateSystem`
(`echarts.js:775-780`), and that property holds the **Grid** instance
(`Grid.js:388`), while the Matrix used for layout is stored separately as
`boxCoordinateSystem` (`CoordinateSystem.js:304`). So the hit test runs against the
individual cell's rect via `Grid.prototype.containPoint` → `Cartesian2D.containPoint`
(`Grid.js:274-277`, `Cartesian2D.js:107`), not against the whole matrix. Had
`coordinateSystem: 'matrix'` redirected that property, every click would have resolved
to grid 0.

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
- The scroll must run inside `nextTick`, matching the existing focus-and-scroll
  precedent at `MeasurementPoints.vue:314-318`, so the target exists before scrolling.

**The matrix option must not depend on the focused sequence.** An earlier draft specified
a per-cell `markLine` marking the persisted cursor. That is unaffordable here:
`useEchart.ts:183-187` watches the option ref and calls
`chart.setOption(withPreservedZoom(next, live), true)` — `notMerge`, a full rebuild — and
the composable returns no chart handle, so there is no targeted-update escape hatch. A
`focused`-dependent option therefore rebuilds every grid, axis and series on every cursor
move. Measured cost of that rebuild: **19.4 ms at N=40, 38.6 ms at N=80** (SVG-SSR probe),
against a 16.7 ms frame and on top of the ~25.7 ms the retained detail panes already
spend on the same focus change.

Dropping the persisted marker makes the option a function of the model alone, so the
matrix rebuilds only when the underlying data changes and adds **no per-click cost at
all**. The hover crosshair still crosses every cell via `axisPointer.link`, and the
detail panes below still show the focused sequence. If a persisted marker later proves
necessary, the correct fix is to have `useEchart` expose its chart instance for partial
updates — not to reintroduce the option dependency.

## Honesty constraints

`relationships.ts:203` hardcodes `demoCoupled: true` for every CD↔FDC join. On Phase-1
data both CD drift and FDC drift derive from one per-MSR `health` scalar
(`mock.py:637-646`), so every correlation is a manufactured artifact. A confident
ranked suspect list built on that would be fiction.

- The panel header reuses the **existing** chip from
  `SequenceWorkbench.vue:84-86` — 「데모 데이터 · 방법 검증 불가」. Do not invent new
  wording.
- Cells with `readiness === 'unavailable'` show `평가 불가`, never a number, and are
  excluded from the evidence row. `assess()` (`relationships.ts:79-90`) already
  distinguishes *no pairs* / *n<3* / *constant axis*; that `reason` goes in the tooltip.
- When no param is evaluable, omit the evidence row entirely rather than render it
  empty.

## Failure and empty states

- `hasFdc === false` → CD row only, plus the existing `fdcReason` text. Never an empty
  matrix.
- Pending and error states need nothing new: the matrix mounts inside the workbench's
  existing `v-else` branch (`SequenceWorkbench.vue:36`) and inherits those guards.
- Missing per-sequence values render as gaps (`connectNulls: false`), matching
  `FdcSequenceTrend.vue:93` and `WaferMap.vue:237`. Only the multi-MSR trend connects
  across gaps.

## Performance

The column cap bounds cell *width*, not the number of grids. N grids + N axes + N line
series in one instance, rebuilt with `notMerge`, costs (SVG-SSR probe, five runs):

| N params | Initial render | Rebuild on option change | Heap delta |
| --- | --- | --- | --- |
| 10 | 11.0 ms | 7.8 ms | — |
| 40 | 19.0 ms | 19.4 ms | 20.9 MB |
| 80 | 37.3 ms | 38.6 ms | 54.2 MB |

Mock runs already reach 80 sequences (`mock.py:503`), so the point count per cell is not
small either. With the focus dependency removed (see Interaction), a rebuild happens only
on a genuine data change — a new MSR or a new active parameter — where 20-40 ms is
acceptable and matches what the existing panel stack already costs.

**Unproven:** these are CPU-side SVG-SSR numbers, not browser canvas numbers. Office-scale
smoothness at 40+ params is not verified. Treat a browser performance check at N=40 as a
gate before declaring this ready for office data, and note that ECharts line series opt
out of progressive rendering (`LineSeries.js:135`), so there is no incremental-draw relief.

## Testing

`app/utils/skewvoirAnalysis/paramMatrix.test.ts`, run by `node --test` per the repo's
72 existing util tests:

- row grouping and Korean label resolution from `fdc_params`
- within-row ordering by |r| descending, with name as a stable tie-break
- evidence row caps at `min(MAX_EVIDENCE, MAX_COLUMNS)` and excludes unevaluable params
- evidence row omitted when nothing is evaluable
- column count equals `min(MAX_COLUMNS, widestRow)`
- a category exceeding `MAX_COLUMNS` wraps onto continuation rows without widening the
  matrix, and every one of its params still appears exactly once
- CD row present even when `hasFdc` is false

The component gets no unit test. The repo has zero component tests; this change does
not start that convention. Verify it visually through the `/verify` skill.

## Resolved: a grid can span multiple matrix cells

The CD row spans the full matrix width via a range coord — `coord: [[0, columns - 1], 0]`.
This was traced through the installed source rather than assumed, because the upstream
example only ever places grids at single cells:

1. `lib/coord/cartesian/Grid.js:152` calls `createBoxLayoutReference(gridModel, api)`,
   so a grid does participate in box layout.
2. `lib/util/layout.js:357-361` calls `boxCoordSys.dataToLayout(coord)` and takes
   `result.contentRect || result.rect` as the grid's reference container.
3. `lib/coord/matrix/Matrix.js:151-173` — `dataToLayout` runs the coord through
   `parseCoordRangeOption`, then `xyLocatorRangeToRectOneDim` for both dimensions.

`parseCoordRangeOption` is the same function that resolves `[[2, 5], 8]`-style ranges
for matrix body cells, so a range coord on a grid resolves to a rect spanning those
cells. `lib/core/CoordinateSystem.js:162` states the intent directly: *"grid rect
(cartesian rect) is calculate based on matrix/calendar coord sys"*.

No fallback is needed. Should the range coord still misbehave at runtime, the CD row
degrades to a single-cell grid at column 0 without affecting anything else — the shared
`dataZoom: { xAxisIndex: 'all' }` is indifferent to grid placement.

## Deferred

- **`set` scope matrix** (rows = param, columns = MSR) — the natural second use of the
  same component, once the single-MSR version proves out. `ParamMatrix.vue` takes a
  model rather than the analysis object specifically to keep that door open.
- **Replacing the stacked panels.** The matrix is an overview layer; the panels keep
  the detailed reading (per-pane stats meta: start/end/range/slope/결측).
