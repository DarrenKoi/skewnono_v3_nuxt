# Skewvoir Wafer Map Enhancement — Design

Date: 2026-07-16
Scope: `측정 개요` (Dashboard) view wafer map on the skewvoir analysis page.

## Problem

The analysis-page wafer map (`components/ebeam/skewvoir/WaferMap.vue`, wrapped by
`dashboard/WaferMap.vue`) shows a single measurement's spatial CD distribution but
is hard to read:

- No measurement-point info on hover — you can't tell which die/field or MP a point belongs to.
- The two view modes are named **Sites** / **Field**, but at this company **Site** and
  **Field** are used interchangeably, so the names are ambiguous.
- No spatial reference lines — position is only readable via the sparse tooltip.
- The color scale is a tiny DOM gradient with no tick values; wafer orientation is unmarked.

## Goals

1. Rename the ambiguous view modes.
2. Add a rich hover tooltip that includes **field (die) info**.
3. Add optional **axis / reference lines** (center crosshair + die-index grid), matching the
   demonstration wafer map (numbered grid).
4. Add extra reading options: color-scale bar, MP-number labels, adjustable color range, notch marker.
5. Provide an **enlarged detail view** in a modal for the demo-style full grid.

## Non-goals

- No changes to `위치 비교` (Position Stack / `WaferHeatChart.vue`) or `상관 / 분포`
  (Correlation) views in this pass. New chrome is built **reusable** so those views can opt in
  later, but they are not touched here.
- No backend / mock-data changes. All fields needed already exist on `MsrFileRow`.

## Domain grounding

From the mock and `MsrFileRow`:

- `chip_number` = die **index** `"col,row"` (e.g. `"3,5"`) — the reticle **field/die**.
- `stage_coordinate` = physical measured position (nm, corner origin) — the actual measurement **point**.
- `mp_number` = measurement-point index within a die (0–29).
- `sequence` = measurement order (identity).
- Geometry: `WaferGeometry` carries `radiusMm`, `pitchXmm`, `pitchYmm` (`utils/waferGeometry.ts`).

## Decisions (from brainstorming)

| Decision | Choice |
| --- | --- |
| Mode names | **Field** (dots at measured positions) / **Die** (filled die tiles) |
| Reference lines | Center crosshair AND die-index grid, each independently toggleable |
| Tooltip fields | Field (die index), MP number, value + parameter |
| Extra options | Color-scale bar, MP-number labels, adjustable color range, notch marker |
| Enlarge | Shared "wafer detail" modal (reusable; Dashboard uses it now) |
| Reach | Dashboard wafer map now; reusable pieces for Position Stack later |

## Terminology rename

- Leaf `WaferMap.vue` prop `mode: 'Sites' | 'Field'` → **`mode: 'Field' | 'Die'`** (default `'Field'`).
  - `'Field'` = dot-per-measured-position view (was `'Sites'`).
  - `'Die'` = filled die-tile view (was `'Field'`).
  - The tile-render branch flips from `mode === 'Field'` to `mode === 'Die'`.
- Wrapper `dashboard/WaferMap.vue` toggle `['Sites', 'Field']` → `['Field', 'Die']`, default `'Field'`.
- Panel meta `"{param} · N sites"` → `"{param} · N fields"`.

## Options model

New shared contract in `app/utils/waferMapOptions.ts`:

```ts
export interface WaferMapOptions {
  crosshair: boolean          // X=0 / Y=0 lines through wafer center
  grid: boolean               // die-index gridlines + axis labels
  mpLabels: boolean           // print mp_number on each point
  notch: boolean              // wafer notch marker (orientation)
  colorMode: 'auto' | 'manual'
  colorMin: number | null     // used when colorMode === 'manual'
  colorMax: number | null
}

export const defaultWaferMapOptions = (): WaferMapOptions => ({
  crosshair: false, grid: false, mpLabels: false, notch: true,
  colorMode: 'auto', colorMin: null, colorMax: null,
})

// Modal opens with the demo-style grid on:
export const detailWaferMapOptions = (): WaferMapOptions => ({
  ...defaultWaferMapOptions(), grid: true,
})
```

Options state is owned by the wrapper (panel) and, independently, by the modal (its own copy so
the compact panel never gains a grid just because the modal was opened).

## Rich tooltip (leaf)

Extend the die aggregate to carry identity fields, then format the tooltip.

- `Die` interface gains `field: string` (= `chip_number`) and `mp: number` (representative
  `mp_number`); it already tracks `n` (measurement count) and `seqs`.
- Tooltip formatter output:

  ```text
  seq {sequence}
  Field  {chip_number}            ← die index ("field info")
  MP     {mp}   | avg of {n} pts  ← "avg of N pts" when n > 1
  {parameter}: {value} {unit}     | 측정 실패
  ```

- Implementation: build a `Map<number, { field, mp, n }>` keyed by representative sequence; the
  formatter reads it via `params.name` (which already carries the sequence string). No change to
  the plotted `value` triples.

## Reference lines (leaf)

Both are independent, driven by `options`:

- **Crosshair** (`options.crosshair`): a silent `markLine` with `{ xAxis: 0 }` and `{ yAxis: 0 }`,
  thin dashed in `SK_CHART.muted`. Off by default.
- **Grid + die-index labels** (`options.grid`): when on,
  - `xAxis`/`yAxis`: `splitLine.show = true` (light), `axisLabel.show = true`,
    `axisTick.show = true`.
  - Axis labels formatted as **die indices** via a new `mmToDieIndex(mm, pitchMm)` helper
    (`Math.round(mm / pitchMm)`), with `interval` set to the pitch so labels land on die columns/rows.
  - `grid.containLabel = true` so labels don't clip; the inscribed circle shrinks slightly while grid is on.
  - **Fallback:** when `pitchXmm`/`pitchYmm` is 0 (unknown), the grid shows plain **mm** ticks instead
    of die indices (still useful). This fallback is explicit, not silent.

## Color-scale bar

New `components/ebeam/skewvoir/ColorScaleBar.vue` — a dumb, reusable horizontal bar:

- Props: `min: number`, `max: number`, `unit: string`, `colors?: string[]` (defaults to `SK_CHART.scale`).
- Renders a gradient with **min / mid / max** tick labels + unit.
- Rendered in the DOM **below** the chart (never overlaps the inscribed circle), replacing the
  current tiny gradient legend in the panel; rendered larger in the modal.
- The `✕` (측정 실패) / `◎` (이상) symbol legend stays alongside it.

## Adjustable color range

- The gear popover exposes `colorMode` as an **Auto / Manual** segmented control.
- **Manual** reveals two number inputs (min / max) seeded from the current auto range
  (the leaf already emits `rangechange` with the data min/max).
- Effective range = manual values when `colorMode === 'manual'`, else the auto data range. The
  wrapper passes the effective `colorMin` / `colorMax` to the leaf's `visualMap` and to `ColorScaleBar`.
- Leaf: `visualMap.min/max` use the override when provided, else the computed `valueRange`.

## Notch marker (leaf)

- `options.notch` (default **on**): draw a small notch at 6 o'clock (0, −R) on the wafer outline —
  a short inward tick / small triangle marker — so orientation is unambiguous (standard 300 mm notch-down).
- Implemented as a tiny extra marker series at the bottom of the outline; silent, `z` above the outline.

## MP-number labels (leaf)

- `options.mpLabels` (default **off**): show `mp_number` as a small label on each point (`series.label`).
- Readability caveat noted in code: dense at the compact panel size; primarily useful in the modal.

## Controls & enlarge (wrapper + modal)

- **Gear ⚙ popover** in the `PanelFrame` `actions` slot → new
  `components/ebeam/skewvoir/WaferMapOptions.vue`: `v-model:options` with checkboxes
  (crosshair, grid, MP labels, notch) + the Auto/Manual color-range control.
- **Enlarge ⤡ button** in the `actions` slot → new shared
  `components/ebeam/skewvoir/WaferDetailModal.vue` (`UModal`): a large wafer map composing the leaf
  `WaferMap` + `ColorScaleBar` + `WaferMapOptions`, opening with `detailWaferMapOptions()` (grid on).
  Built reusable so Position Stack's heat maps can open it later; only the Dashboard wires it in this pass.
- Panel wafer square grows from `max-w-[17rem]` to `~max-w-[22rem]`; the sibling radius plot keeps the
  remaining column height (`flex-1`).

## Component boundaries

| Unit | Responsibility | Change |
| --- | --- | --- |
| `WaferMap.vue` (leaf) | Pure renderer; new `options` + `colorMin`/`colorMax` props; rich tooltip; crosshair / grid / notch / mpLabels | modify |
| `ColorScaleBar.vue` | Dumb ticked color bar, shared by panel + modal | new |
| `WaferMapOptions.vue` | Gear popover body, `v-model:options` | new |
| `WaferDetailModal.vue` | Shared enlarge view composing leaf + bar + options | new |
| `dashboard/WaferMap.vue` (wrapper) | Owns panel options + effective range, gear + enlarge buttons, renders leaf + bar | modify |
| `utils/waferMapOptions.ts` | `WaferMapOptions` type + `defaultWaferMapOptions` / `detailWaferMapOptions` | new |
| `utils/waferGeometry.ts` | `mmToDieIndex(mm, pitchMm)` helper | modify |

## Data flow

```text
dashboard/WaferMap.vue (panel)
  ├─ options: ref<WaferMapOptions>            ← gear popover (WaferMapOptions.vue) mutates
  ├─ autoRange: ref                           ← leaf @rangechange
  ├─ effectiveRange = manual ? {min,max} : autoRange
  ├─ <WaferMap :options :color-min :color-max @rangechange @focus />
  ├─ <ColorScaleBar :min :max :unit />
  └─ ⤡ → <WaferDetailModal>                   ← own options copy (grid on)
            └─ <WaferMap …> + <ColorScaleBar> + <WaferMapOptions>
```

## Testing (Vitest + Vue Test Utils)

- `waferGeometry.test.ts`: `mmToDieIndex` — rounds mm→index; handles pitch 0 (returns null / mm passthrough).
- Leaf `WaferMap`:
  - mode union rename: `'Die'` renders tiles, `'Field'` renders dots (no `'Sites'` regressions).
  - tooltip builder produces `field` + `mp` (+ "avg of N pts" when `n > 1`).
  - `options.crosshair` adds the x/y `markLine`; `options.grid` enables axis labels with the
    die-index formatter (and mm fallback when pitch is 0); `options.notch` adds the marker.
  - manual `colorMin`/`colorMax` override the visualMap range.
- Wrapper: gear toggles mutate options; Auto→Manual seeds inputs from auto range; enlarge opens the modal.

## Rollout

Single implementation plan. Suggested build order:
1. `waferMapOptions.ts` + `mmToDieIndex` (+ tests).
2. Terminology rename (leaf + wrapper + meta), keep behavior identical.
3. Rich tooltip.
4. `ColorScaleBar.vue`; swap panel legend to it.
5. Reference lines (crosshair, grid), notch, mpLabels in the leaf, gated by `options`.
6. `WaferMapOptions.vue` popover + wire into wrapper; adjustable color range.
7. `WaferDetailModal.vue` + enlarge button; panel height bump.
8. Tests + `npm run lint:md` for this doc.
