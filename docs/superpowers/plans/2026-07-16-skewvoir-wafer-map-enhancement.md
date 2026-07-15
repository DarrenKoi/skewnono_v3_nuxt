# Skewvoir Wafer Map Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Consensus revisions (post-Codex review, 2026-07-16)

A second-opinion review (Codex) surfaced 8 issues; verified against source, these were reconciled
as follows. **The revisions below override the original tasks where they conflict.**

**Accepted:**

1. **Per-point Field mode (was blocking).** `mock.py:500` cycles `dies[(sequence-1) % len(dies)]`, so
   multiple measured rows share a die at distinct stage positions / MPs. The current leaf averages
   them into one dot per die — you can't hover an individual point. Fix: extract a pure
   `buildWaferPoints(rows, geo)` (new `app/utils/waferPoints.ts`, tested) returning **`fieldPoints`**
   (one per measured row) + **`diePoints`** (aggregated per die) + `failurePoints`, all in one unified
   shape `{ seq, field, mp, n, seqs, x, y, value }`. Field mode plots `fieldPoints`; Die mode plots
   `diePoints`. This also satisfies Codex #4a (test the risky data logic).
2. **Die-aligned grid (was blocking).** `buildWaferAxis` uses `interval: pitchMm` (guarded > 0) so
   gridlines align to die pitch, not arbitrary auto-ticks. Extracted to pure `app/utils/waferAxis.ts`
   (tested).
3. **Preserve the circle (was blocking).** Keep `grid.containLabel: false`; when grid is on use
   symmetric enlarged margins (equal on all sides) so the plot rect stays square and the wafer stays
   circular. `containLabel: true` is *not* used.
4. **Notch orientation (was blocking).** Drop `symbolRotate: 180`; ECharts' default `triangle` points
   up = inward at the 6 o'clock (0, −R) position.
5. **Robust manual range (was blocking).** `resolveColorRange` guards with `Number.isFinite` (empty
   `UInput` → `''`/`NaN` no longer slips through). The popover receives the current auto range and
   **seeds** `colorMin`/`colorMax` when switching to Manual.
6. **Typecheck gate.** Final verification adds `npm --prefix front-dev-home run typecheck`.

**Rejected / deferred (with reason):**

- **Meta "N fields" count (Codex #2b):** kept as measured-row count. Per the user's vocabulary
  Field = measurement point/site, so `N fields` = number of measured points = rows. Codex assumed
  field = die; the user's terminology makes the row count correct.
- **Failure-row tooltip field info (#1d):** `formatWaferTooltip` already degrades gracefully (omits
  Field/MP when null). Left as a later enhancement.
- **Immutable `update:options` emit (#3b):** deep-ref mutation works for both current parents;
  non-blocking. Kept.
- **Nested UPopover-in-UModal stacking (#3c):** no code change; added a manual browser verification step.

Two new util tasks (`waferPoints.ts`, `waferAxis.ts`) precede the leaf edits; the leaf (Task 7) consumes
them instead of the inline `dies`/`buildAxis` logic in the original draft.

**Goal:** Make the 측정 개요 (Dashboard) wafer map on the skewvoir analysis page readable and richer — unambiguous mode names, a field/MP hover tooltip, optional crosshair + die-index grid, a notch marker, a ticked color bar, adjustable color range, and a shared enlarge modal.

**Architecture:** Extract all testable logic into pure `app/utils/*.ts` helpers (tested with `node --test`, this repo's only test style — there are no Vue component tests). The leaf `WaferMap.vue` becomes an options-driven pure renderer; a wrapper panel owns option state and a gear popover; a shared `WaferDetailModal.vue` hosts the enlarged demo-style grid. New chrome (color bar, options popover, modal) is built reusable so Position Stack can adopt it later, but no cross-wafer view is touched in this pass.

**Tech Stack:** Nuxt 4 SPA, Vue 3 `<script setup>`, NuxtUI (`UModal`, `UPopover`, `UCheckbox`, `UInput`, `UButton`, `UIcon`), ECharts via `useEchart`, `node:test` + `node:assert/strict` for pure-logic tests.

## Global Constraints

- Tests use `node:test` + `node:assert/strict`, run via `npm --prefix front-dev-home test` (glob `app/**/*.test.ts`). No Vue component tests exist — do not add a component-test framework.
- Lint gates: `npm --prefix front-dev-home run lint` (eslint) for code; `npm run lint:md` (repo root) for Markdown.
- Mode names are exactly **`'Field'`** (dots at measured positions) and **`'Die'`** (filled die tiles). Default `'Field'`.
- Chart tokens come from `SK_CHART` (`app/utils/chartPalette.ts`): `scale` (5-stop ramp), `series` `#5C86AE`, `muted` `#9A8E7C`, `ink` `#15110D`, `bad` `#C4453B`.
- Geometry helpers live in `app/utils/waferGeometry.ts`; `WaferGeometry` has `radiusMm`, `pitchXmm`, `pitchYmm` (0 when unknown).
- Korean UI copy uses formal endings; existing labels (`측정 실패`, `이상`) stay verbatim.
- CSR-only app; no SSR/hydration concerns.
- Commit after each task. Do **not** push (user pushes manually).

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `app/utils/waferMapOptions.ts` | `WaferMapOptions` type, default/detail factories, `resolveColorRange` | create |
| `app/utils/waferMapOptions.test.ts` | Tests for the above | create |
| `app/utils/waferGeometry.ts` | Add `mmToDieIndex(mm, pitchMm)` | modify |
| `app/utils/waferGeometry.test.ts` | Tests for `mmToDieIndex` | modify |
| `app/utils/waferTooltip.ts` | `formatWaferTooltip(input)` pure HTML builder | create |
| `app/utils/waferTooltip.test.ts` | Tests for the tooltip builder | create |
| `app/components/ebeam/skewvoir/WaferMap.vue` | Leaf renderer: mode rename, options, tooltip, crosshair/grid/notch/mpLabels, color override | modify |
| `app/components/ebeam/skewvoir/ColorScaleBar.vue` | Dumb ticked color bar (panel + modal) | create |
| `app/components/ebeam/skewvoir/WaferMapOptions.vue` | Gear popover body, `v-model:options` | create |
| `app/components/ebeam/skewvoir/WaferDetailModal.vue` | Shared enlarge view | create |
| `app/components/ebeam/skewvoir/dashboard/WaferMap.vue` | Wrapper: option state, gear + enlarge buttons, color bar, height bump | modify |

---

## Task 1: Options model util

**Files:**
- Create: `app/utils/waferMapOptions.ts`
- Test: `app/utils/waferMapOptions.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `interface WaferMapOptions { crosshair: boolean; grid: boolean; mpLabels: boolean; notch: boolean; colorMode: 'auto' | 'manual'; colorMin: number | null; colorMax: number | null }`
  - `defaultWaferMapOptions(): WaferMapOptions`
  - `detailWaferMapOptions(): WaferMapOptions`
  - `resolveColorRange(mode: 'auto' | 'manual', manualMin: number | null, manualMax: number | null, auto: { min: number, max: number }): { min: number, max: number }`

- [ ] **Step 1: Write the failing test**

Create `app/utils/waferMapOptions.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { defaultWaferMapOptions, detailWaferMapOptions, resolveColorRange } from './waferMapOptions.ts'

test('defaultWaferMapOptions: notch on, everything else off, auto color', () => {
  const o = defaultWaferMapOptions()
  assert.equal(o.crosshair, false)
  assert.equal(o.grid, false)
  assert.equal(o.mpLabels, false)
  assert.equal(o.notch, true)
  assert.equal(o.colorMode, 'auto')
  assert.equal(o.colorMin, null)
  assert.equal(o.colorMax, null)
})

test('detailWaferMapOptions: like default but grid on', () => {
  const o = detailWaferMapOptions()
  assert.equal(o.grid, true)
  assert.equal(o.notch, true)
})

test('resolveColorRange: auto mode returns the auto range', () => {
  assert.deepEqual(resolveColorRange('auto', 1, 9, { min: 3, max: 7 }), { min: 3, max: 7 })
})

test('resolveColorRange: valid manual overrides auto', () => {
  assert.deepEqual(resolveColorRange('manual', 1, 9, { min: 3, max: 7 }), { min: 1, max: 9 })
})

test('resolveColorRange: manual falls back to auto when incomplete or inverted', () => {
  assert.deepEqual(resolveColorRange('manual', null, 9, { min: 3, max: 7 }), { min: 3, max: 7 })
  assert.deepEqual(resolveColorRange('manual', 9, 1, { min: 3, max: 7 }), { min: 3, max: 7 })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test 2>&1 | grep waferMapOptions`
Expected: FAIL — cannot find module `./waferMapOptions.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `app/utils/waferMapOptions.ts`:

```ts
// Display options for the skewvoir wafer map. Shared by the leaf renderer,
// the panel wrapper, the gear popover, and the detail modal so every surface
// speaks the same option contract.
export interface WaferMapOptions {
  crosshair: boolean // X=0 / Y=0 lines through wafer centre
  grid: boolean // die-index gridlines + axis labels
  mpLabels: boolean // print mp_number on each point (Field mode)
  notch: boolean // wafer notch marker (orientation)
  colorMode: 'auto' | 'manual'
  colorMin: number | null // used when colorMode === 'manual'
  colorMax: number | null
}

export const defaultWaferMapOptions = (): WaferMapOptions => ({
  crosshair: false,
  grid: false,
  mpLabels: false,
  notch: true,
  colorMode: 'auto',
  colorMin: null,
  colorMax: null
})

// The enlarge modal opens with the demo-style numbered grid on.
export const detailWaferMapOptions = (): WaferMapOptions => ({
  ...defaultWaferMapOptions(),
  grid: true
})

// Effective color-scale range: a complete, non-inverted manual pair wins;
// otherwise fall back to the data-derived auto range.
export const resolveColorRange = (
  mode: 'auto' | 'manual',
  manualMin: number | null,
  manualMax: number | null,
  auto: { min: number, max: number }
): { min: number, max: number } => {
  if (mode === 'manual' && manualMin != null && manualMax != null && manualMin < manualMax) {
    return { min: manualMin, max: manualMax }
  }
  return auto
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix front-dev-home test 2>&1 | grep -E 'waferMapOptions|# fail'`
Expected: the 5 waferMapOptions tests pass; `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/waferMapOptions.ts front-dev-home/app/utils/waferMapOptions.test.ts
git commit -m "feat(skewvoir): add wafer-map options model + color-range resolver"
```

---

## Task 2: `mmToDieIndex` geometry helper

**Files:**
- Modify: `app/utils/waferGeometry.ts`
- Test: `app/utils/waferGeometry.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `mmToDieIndex(mm: number, pitchMm: number): number | null` — die index for a mm coordinate, or `null` when pitch is unknown (`<= 0`).

- [ ] **Step 1: Write the failing test**

Append to `app/utils/waferGeometry.test.ts` (add `mmToDieIndex` to the existing import on line 4):

```ts
import { parseWaferGeometry, stagePosMm, dieCenterMm, siteRadiusMm, mmToDieIndex } from './waferGeometry.ts'

test('mmToDieIndex rounds mm to the nearest die column/row', () => {
  assert.equal(mmToDieIndex(0, 6.818182), 0)
  assert.equal(mmToDieIndex(6.9, 6.818182), 1)
  assert.equal(mmToDieIndex(-13.6, 6.818182), -2)
})

test('mmToDieIndex returns null when pitch is unknown', () => {
  assert.equal(mmToDieIndex(50, 0), null)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test 2>&1 | grep -iE 'mmToDieIndex|SyntaxError|not.*export'`
Expected: FAIL — `mmToDieIndex` is not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `app/utils/waferGeometry.ts`:

```ts
// Convert a physical mm coordinate to its die-grid index (col or row). Returns
// null when the pitch is unknown so callers can fall back to mm labels.
export const mmToDieIndex = (mm: number, pitchMm: number): number | null =>
  pitchMm > 0 ? Math.round(mm / pitchMm) : null
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix front-dev-home test 2>&1 | grep -E 'mmToDieIndex|# fail'`
Expected: both new tests pass; `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/waferGeometry.ts front-dev-home/app/utils/waferGeometry.test.ts
git commit -m "feat(skewvoir): add mmToDieIndex helper for die-index axis labels"
```

---

## Task 3: Tooltip formatter util

**Files:**
- Create: `app/utils/waferTooltip.ts`
- Test: `app/utils/waferTooltip.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `interface WaferTooltipInput { seq: string; field: string | null; mp: number | null; n: number; param: string; value: number | null; unit: string }`
  - `formatWaferTooltip(i: WaferTooltipInput): string` — HTML string for the ECharts tooltip. Omits Field/MP lines when null; shows `측정 실패` when `value` is null; appends `· avg of N pts` when `n > 1`.

- [ ] **Step 1: Write the failing test**

Create `app/utils/waferTooltip.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatWaferTooltip } from './waferTooltip.ts'

test('measured point shows seq, field, mp, and value', () => {
  const html = formatWaferTooltip({ seq: '42', field: '3,5', mp: 7, n: 1, param: 'CD_X', value: 48.2, unit: 'nm' })
  assert.match(html, /seq 42/)
  assert.match(html, /Field 3,5/)
  assert.match(html, /MP 7/)
  assert.match(html, /CD_X: <b>48.2<\/b> nm/)
  assert.doesNotMatch(html, /avg of/)
})

test('averaged die appends the point count', () => {
  const html = formatWaferTooltip({ seq: '1', field: '0,0', mp: 3, n: 4, param: 'CD_X', value: 50, unit: 'nm' })
  assert.match(html, /MP 3 · avg of 4 pts/)
})

test('failure shows 측정 실패 and no value block', () => {
  const html = formatWaferTooltip({ seq: '9', field: null, mp: null, n: 1, param: 'CD_X', value: null, unit: 'nm' })
  assert.match(html, /seq 9/)
  assert.match(html, /측정 실패/)
  assert.doesNotMatch(html, /Field/)
  assert.doesNotMatch(html, /MP/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test 2>&1 | grep -iE 'waferTooltip|not.*found'`
Expected: FAIL — cannot find module `./waferTooltip.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `app/utils/waferTooltip.ts`:

```ts
// Builds the wafer-map hover tooltip HTML. Kept pure (no ECharts types) so it
// can be unit-tested; the leaf component feeds it per-point identity + value.
export interface WaferTooltipInput {
  seq: string
  field: string | null // chip_number (die index) — the "field info"
  mp: number | null // representative mp_number for the die
  n: number // measurements aggregated into this point
  param: string
  value: number | null // null → measurement failure
  unit: string
}

export const formatWaferTooltip = (i: WaferTooltipInput): string => {
  const lines: string[] = [`seq ${i.seq}`]
  if (i.field != null) lines.push(`Field ${i.field}`)
  if (i.mp != null) lines.push(i.n > 1 ? `MP ${i.mp} · avg of ${i.n} pts` : `MP ${i.mp}`)
  lines.push(i.value != null ? `${i.param}: <b>${i.value}</b> ${i.unit}` : '측정 실패')
  return lines.join('<br/>')
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix front-dev-home test 2>&1 | grep -E 'waferTooltip|# fail'`
Expected: 3 tests pass; `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/waferTooltip.ts front-dev-home/app/utils/waferTooltip.test.ts
git commit -m "feat(skewvoir): add wafer tooltip formatter with field/MP info"
```

---

## Task 4: Terminology rename (Field / Die)

Behavior-preserving rename of the two view modes. No new features. Verified by lint + running the app.

**Files:**
- Modify: `app/components/ebeam/skewvoir/WaferMap.vue`
- Modify: `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`

**Interfaces:**
- Consumes: nothing new.
- Produces: leaf prop `mode?: 'Field' | 'Die'` (default `'Field'`). `'Field'` renders dots; `'Die'` renders tiles.

- [ ] **Step 1: Rename the leaf mode union + flip the tile branch**

In `app/components/ebeam/skewvoir/WaferMap.vue`:

Replace the `mode` prop doc + type (lines 22-26):

```ts
  /** 'Field' = colored dots at measured stage positions; 'Die' = filled die tiles. */
  mode?: 'Field' | 'Die'
}>(), {
  mode: 'Field'
})
```

Replace the `valueSeries` mode check (line 145) — tiles now render for `'Die'`:

```ts
const valueSeries = computed(() =>
  props.mode === 'Die'
    ? {
        type: 'custom' as const,
        renderItem: renderTile as never,
        encode: { x: 0, y: 1, tooltip: [0, 1, 2] },
        data: tilePoints.value
      }
    : {
        type: 'scatter' as const,
        symbolSize: 13,
        data: sitePoints.value
      }
)
```

- [ ] **Step 2: Rename the wrapper toggle + default + meta**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`:

Change the PanelFrame toggles (line 6):

```vue
    :toggles="['Field', 'Die']"
```

Change the mode ref default (line 68):

```ts
const mode = ref<'Field' | 'Die'>('Field')
```

Change the meta label (line 90) — "sites" → "fields":

```ts
const meta = computed(() => `${props.analysis.activeParam.value} · ${siteCount.value} fields`)
```

- [ ] **Step 3: Lint**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: no errors for the two WaferMap files.

- [ ] **Step 4: Verify in the running app**

Use the `verify` skill (Flask mock + Nuxt). Open the analysis page → 측정 개요 → confirm the Wafer Map panel toggle now reads **Field | Die**, that **Field** shows dots and **Die** shows filled tiles, and the meta reads `… · N fields`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue
git commit -m "refactor(skewvoir): rename wafer-map modes Sites/Field -> Field/Die"
```

---

## Task 5: Rich hover tooltip in the leaf

Carry `field` (chip_number) + `mp` (mp_number) onto each die aggregate and format the tooltip via `formatWaferTooltip`.

**Files:**
- Modify: `app/components/ebeam/skewvoir/WaferMap.vue`

**Interfaces:**
- Consumes: `formatWaferTooltip` (Task 3).
- Produces: `metaBySeq` map `Map<string, { field: string, mp: number, n: number }>` used by later tasks (mpLabels in Task 7).

- [ ] **Step 1: Import the formatter**

Add to the imports block (after line 13):

```ts
import { formatWaferTooltip } from '~/utils/waferTooltip'
```

- [ ] **Step 2: Extend the `Die` interface + populate field/mp**

Replace the `Die` interface (line 38):

```ts
interface Die { col: number, row: number, sx: number, sy: number, sum: number, n: number, seq: number, mp: number, field: string, seqs: Set<number> }
```

In the `dies` computed, update the default record creation (line 46) to capture `mp` + `field`:

```ts
    const e = acc.get(r.chip_number)
      ?? { col: chip[0], row: chip[1], sx: pos[0], sy: pos[1], sum: 0, n: 0, seq: r.sequence, mp: r.mp_number, field: r.chip_number, seqs: new Set<number>() }
```

- [ ] **Step 3: Build the seq→meta map**

Add after the `dies` computed (after line 53):

```ts
// seq (as string, matching each point's `name`) → identity for the tooltip/labels.
const metaBySeq = computed(() => {
  const m = new Map<string, { field: string, mp: number, n: number }>()
  for (const e of dies.value) m.set(String(e.seq), { field: e.field, mp: e.mp, n: e.n })
  return m
})
```

- [ ] **Step 4: Replace the tooltip formatter**

Replace the `tooltip` block in `option` (lines 160-168):

```ts
  tooltip: {
    formatter: (params) => {
      const p = params as { value?: number[], name?: string }
      const seq = p.name ?? ''
      const meta = metaBySeq.value.get(seq)
      return formatWaferTooltip({
        seq,
        field: meta?.field ?? null,
        mp: meta?.mp ?? null,
        n: meta?.n ?? 1,
        param: props.parameter,
        value: p.value?.[2] ?? null,
        unit: props.unit
      })
    }
  },
```

- [ ] **Step 5: Lint + verify**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: clean.

Then via the `verify` skill: hover a measured point → tooltip shows `seq N`, `Field c,r`, `MP m`, `PARAM: value unit`. Hover a ✕ failure → shows `seq N` + `측정 실패` only.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue
git commit -m "feat(skewvoir): wafer tooltip shows field (die) + MP info"
```

---

## Task 6: ColorScaleBar component + swap panel legend

**Files:**
- Create: `app/components/ebeam/skewvoir/ColorScaleBar.vue`
- Modify: `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`

**Interfaces:**
- Consumes: `SK_CHART` (`~/utils/chartPalette`).
- Produces: `<EbeamSkewvoirColorScaleBar :min :max :unit :colors? />` — a horizontal gradient bar with min/mid/max tick labels + unit.

- [ ] **Step 1: Create the color bar**

Create `app/components/ebeam/skewvoir/ColorScaleBar.vue`:

```vue
<template>
  <!-- Dumb, reusable color-scale legend: gradient + min/mid/max ticks + unit.
       Lives in the DOM (never inside the wafer square) so it can't overlap the
       inscribed circle. Shared by the panel and the detail modal. -->
  <div class="flex flex-col items-center gap-0.5">
    <div
      class="h-2.5 w-full max-w-[16rem] rounded-(--sk-r-sidebar)"
      :style="gradientStyle"
    />
    <div class="flex w-full max-w-[16rem] items-center justify-between font-mono text-[11px] text-(--sk-ink-muted) tabular-nums">
      <span class="text-(--sk-ink)">{{ fmt(min) }}</span>
      <span>{{ fmt((min + max) / 2) }}</span>
      <span class="text-(--sk-ink)">{{ fmt(max) }} {{ unit }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { SK_CHART } from '~/utils/chartPalette'

const props = withDefaults(defineProps<{
  min: number
  max: number
  unit: string
  colors?: string[]
}>(), {
  colors: () => [...SK_CHART.scale]
})

const gradientStyle = computed(() => ({
  background: `linear-gradient(to right, ${props.colors.join(', ')})`
}))
const fmt = (n: number) => (Number.isFinite(n) ? n.toFixed(1) : '—')
</script>
```

- [ ] **Step 2: Swap the wrapper legend to use it**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`, replace the legend gradient span block (lines 38-47) so the color bar replaces the inline gradient, keeping the ✕/◎ symbols:

```vue
      <!-- Legend, separate from the chart so it can't overlap the wafer. -->
      <div class="flex flex-col items-center gap-1">
        <EbeamSkewvoirColorScaleBar
          :min="rangeNums.min"
          :max="rangeNums.max"
          :unit="analysis.activeUnit.value"
        />
        <div class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-mono text-[11px] text-(--sk-ink-muted)">
          <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span>측정 실패</span>
          <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">◎</span>이상</span>
        </div>
      </div>
```

Replace the `gradientStyle` + `rangeLabel` computeds (lines 72-77) with a numeric range the bar consumes:

```ts
const rangeNums = computed(() => colorRange.value ?? { min: 0, max: 1 })
```

Remove the now-unused `SK_CHART` import if nothing else uses it (check line 64 — `isMeasuredRow` stays; drop `SK_CHART`):

```ts
import { isMeasuredRow } from '~/utils/msrRows'
```

- [ ] **Step 3: Lint + verify**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: clean (no unused `SK_CHART`/`gradientStyle`/`rangeLabel`).

Via `verify` skill: the wafer panel shows a color bar with min/mid/max tick values + unit below the map; ✕/◎ legend still present.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/ColorScaleBar.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue
git commit -m "feat(skewvoir): ticked color-scale bar for the wafer map legend"
```

---

## Task 7: Reference lines, notch, MP labels, color override in the leaf

Add the `options` + `colorMin`/`colorMax` props and render crosshair, die-index grid, notch marker, and MP labels accordingly.

**Files:**
- Modify: `app/components/ebeam/skewvoir/WaferMap.vue`

**Interfaces:**
- Consumes: `WaferMapOptions`, `defaultWaferMapOptions` (Task 1); `mmToDieIndex` (Task 2); `metaBySeq` (Task 5).
- Produces: leaf props `options?: WaferMapOptions` (default `defaultWaferMapOptions()`), `colorMin?: number | null`, `colorMax?: number | null` (default `null`).

- [ ] **Step 1: Import the options + geometry helpers**

Update imports (line 13) and add the options import:

```ts
import { stagePosMm, dieCenterMm, mmToDieIndex, type WaferGeometry } from '~/utils/waferGeometry'
import { defaultWaferMapOptions, type WaferMapOptions } from '~/utils/waferMapOptions'
```

- [ ] **Step 2: Add the new props**

Extend the `withDefaults(defineProps<{…}>(), {…})` block — add to the props type (after `mode?`):

```ts
  options?: WaferMapOptions
  colorMin?: number | null
  colorMax?: number | null
```

and to the defaults object:

```ts
}>(), {
  mode: 'Field',
  options: () => defaultWaferMapOptions(),
  colorMin: null,
  colorMax: null
})
```

- [ ] **Step 3: Compute the effective color range**

Add after the `valueRange` computed (after line 100):

```ts
// Manual override (from the panel/modal) wins; else the data range.
const effMin = computed(() => props.colorMin ?? valueRange.value.min)
const effMax = computed(() => props.colorMax ?? valueRange.value.max)
```

- [ ] **Step 4: Build conditional axis config**

Add before the `option` computed (after line 157):

```ts
// Axis furniture is hidden by default (position read via tooltip). When the grid
// option is on, show light splitLines + die-index labels (mm fallback when the
// pitch is unknown). Labels need inner margin, so the grid contains them.
const buildAxis = (pitchMm: number) => (props.options.grid
  ? {
      type: 'value' as const, min: -axisMax.value, max: axisMax.value,
      splitLine: { show: true, lineStyle: { color: SK_CHART.muted, opacity: 0.22 } },
      axisLabel: {
        show: true, color: SK_CHART.muted, fontSize: 9,
        formatter: (v: number) => {
          const i = mmToDieIndex(v, pitchMm)
          return i == null ? String(Math.round(v)) : String(i)
        }
      },
      axisLine: { show: false }, axisTick: { show: true }
    }
  : {
      type: 'value' as const, min: -axisMax.value, max: axisMax.value,
      splitLine: { show: false }, axisLabel: { show: false },
      axisLine: { show: false }, axisTick: { show: false }
    })
```

- [ ] **Step 5: Wire grid/crosshair/notch/mpLabels/color into `option`**

In the `option` computed, replace the `grid`, `xAxis`, `yAxis`, `visualMap` entries (lines 171-181):

```ts
  grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: props.options.grid },
  xAxis: buildAxis(props.geo.pitchXmm),
  yAxis: buildAxis(props.geo.pitchYmm),
  visualMap: {
    show: false,
    min: effMin.value, max: effMax.value,
    dimension: 2, seriesIndex: 0, inRange: { color: [...SK_CHART.scale] }
  },
```

Add MP labels onto the dot series — change `valueSeries` (Task 4 version) so the `scatter` branch carries a conditional label:

```ts
    : {
        type: 'scatter' as const,
        symbolSize: 13,
        data: sitePoints.value,
        label: props.options.mpLabels
          ? {
              show: true, position: 'top', fontSize: 9, color: SK_CHART.ink,
              formatter: (p: { name?: string }) => {
                const m = metaBySeq.value.get(p.name ?? '')
                return m ? String(m.mp) : ''
              }
            }
          : undefined
      }
```

Add crosshair `markLine` to the wafer-outline series and append a notch series. Replace the `series` array (lines 182-193):

```ts
  series: [
    valueSeries.value,
    { type: 'line', data: waferOutline.value, showSymbol: false, silent: true,
      lineStyle: { color: SK_CHART.muted, width: 1.25, opacity: 0.55 }, tooltip: { show: false }, z: 0,
      ...(props.options.crosshair
        ? { markLine: { silent: true, symbol: 'none',
            lineStyle: { color: SK_CHART.muted, type: 'dashed', width: 1, opacity: 0.5 },
            label: { show: false }, data: [{ xAxis: 0 }, { yAxis: 0 }] } }
        : {}) },
    ...(props.options.notch
      ? [{ type: 'scatter' as const, symbol: 'triangle', symbolSize: 9, symbolRotate: 180,
          data: [[0, -waferRadius.value]], itemStyle: { color: SK_CHART.muted },
          silent: true, z: 1, tooltip: { show: false } }]
      : []),
    { type: 'scatter', symbol: 'circle', symbolSize: 24, data: outlierPoints.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.bad, borderWidth: 2 }, silent: true, z: 4 },
    { type: 'scatter', symbolSize: 13, data: failurePoints.value,
      itemStyle: { color: 'transparent' },
      label: { show: true, formatter: '✕', color: SK_CHART.bad, fontSize: 13, fontWeight: 'bold' }, z: 4 },
    { type: 'scatter', symbol: 'circle', symbolSize: 19, data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 }, silent: true, z: 5 }
  ]
```

- [ ] **Step 6: Lint + verify**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: clean.

Temporarily pass `:options="{ ...defaultWaferMapOptions(), crosshair: true, grid: true, mpLabels: true }"` from the wrapper (or verify in Task 9's modal). Via `verify` skill confirm: crosshair through centre, die-index axis labels, notch triangle at bottom, mp labels on dots. Then revert any temporary override.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue
git commit -m "feat(skewvoir): wafer-map crosshair, die-index grid, notch, MP labels, color override"
```

---

## Task 8: Options popover + wire into the wrapper (gear + adjustable range)

**Files:**
- Create: `app/components/ebeam/skewvoir/WaferMapOptions.vue`
- Modify: `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`

**Interfaces:**
- Consumes: `WaferMapOptions` (Task 1).
- Produces: `<EbeamSkewvoirWaferMapOptions v-model:options="…" />` — a gear-triggered popover with checkboxes (crosshair, grid, MP labels, notch) + an Auto/Manual color-range control with min/max inputs.

- [ ] **Step 1: Create the popover**

Create `app/components/ebeam/skewvoir/WaferMapOptions.vue`:

```vue
<template>
  <UPopover :content="{ align: 'end' }">
    <UButton
      icon="i-lucide-settings-2"
      color="neutral"
      variant="ghost"
      size="xs"
      :aria-label="'표시 옵션'"
    />
    <template #content>
      <div class="w-56 space-y-2.5 p-3">
        <p class="sk-label">표시 옵션</p>
        <div class="space-y-1.5">
          <UCheckbox v-model="model.crosshair" label="중심선 (crosshair)" size="xs" />
          <UCheckbox v-model="model.grid" label="격자 · Die 번호" size="xs" />
          <UCheckbox v-model="model.mpLabels" label="MP 번호 표시" size="xs" />
          <UCheckbox v-model="model.notch" label="Notch 표시" size="xs" />
        </div>

        <div class="border-t border-(--sk-border-soft) pt-2.5">
          <p class="sk-label mb-1.5">색상 범위</p>
          <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
            <button
              v-for="m in (['auto', 'manual'] as const)"
              :key="m"
              type="button"
              class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
              :class="model.colorMode === m
                ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
                : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="model.colorMode = m"
            >
              {{ m === 'auto' ? 'Auto' : 'Manual' }}
            </button>
          </div>
          <div
            v-if="model.colorMode === 'manual'"
            class="mt-2 flex items-center gap-1.5"
          >
            <UInput v-model.number="model.colorMin" type="number" size="xs" placeholder="min" class="w-full" />
            <span class="text-(--sk-ink-subtle)">–</span>
            <UInput v-model.number="model.colorMax" type="number" size="xs" placeholder="max" class="w-full" />
          </div>
        </div>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import type { WaferMapOptions } from '~/utils/waferMapOptions'

// v-model:options — the parent owns the option object; this popover mutates it.
const model = defineModel<WaferMapOptions>('options', { required: true })
</script>
```

- [ ] **Step 2: Wire the popover + effective range into the wrapper**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`:

Add an `actions` slot to `PanelFrame` (immediately after the opening `<EbeamSkewvoirPanelFrame …>` tag's props, before its default content — insert after line 8 `body-class="…"` closes the tag at line 9). Insert as the first child:

```vue
    <template #actions>
      <EbeamSkewvoirWaferMapOptions v-model:options="options" />
    </template>
```

Pass options + effective color range to the leaf (replace lines 28-32 region):

```vue
            :mode="mode"
            :options="options"
            :color-min="effectiveRange.colorMin"
            :color-max="effectiveRange.colorMax"
            :focused-sequence="analysis.focusedSequence.value"
            :outlier-seqs="outlierSeqs"
            @focus="analysis.setFocusedSequence"
            @rangechange="colorRange = $event"
```

Update the `<script setup>` — add imports + option state + effective-range derivation (near line 66):

```ts
import { defaultWaferMapOptions, resolveColorRange } from '~/utils/waferMapOptions'

const options = ref(defaultWaferMapOptions())

// The leaf publishes the auto (data) range via @rangechange; the manual override
// from the popover is applied here and fed back to the leaf's visualMap + bar.
const effectiveRange = computed(() => {
  const auto = colorRange.value ?? { min: 0, max: 1 }
  const r = resolveColorRange(options.value.colorMode, options.value.colorMin, options.value.colorMax, auto)
  return { colorMin: r.min, colorMax: r.max }
})
```

Update `rangeNums` (from Task 6) so the color bar reflects the effective (possibly manual) range:

```ts
const rangeNums = computed(() => ({ min: effectiveRange.value.colorMin, max: effectiveRange.value.colorMax }))
```

- [ ] **Step 3: Lint + verify**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: clean.

Via `verify` skill: a gear button appears in the panel header; opening it toggles crosshair/grid/MP labels/notch live on the map; switching color range to Manual with min/max recolors the map and updates the color bar.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMapOptions.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue
git commit -m "feat(skewvoir): wafer-map options popover with reference lines + color range"
```

---

## Task 9: Shared detail modal + enlarge button + height bump

**Files:**
- Create: `app/components/ebeam/skewvoir/WaferDetailModal.vue`
- Modify: `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`

**Interfaces:**
- Consumes: leaf `WaferMap` props (Tasks 4-7), `ColorScaleBar` (Task 6), `WaferMapOptions` (Task 8), `detailWaferMapOptions` (Task 1), `MsrFileRow` + `WaferGeometry` types.
- Produces: `<EbeamSkewvoirWaferDetailModal v-model:open="…" :rows :parameter :unit :geo :focused-sequence :outlier-seqs @focus />` — a large wafer view opening with `detailWaferMapOptions()`.

- [ ] **Step 1: Create the modal**

Create `app/components/ebeam/skewvoir/WaferDetailModal.vue`:

```vue
<template>
  <UModal
    v-model:open="open"
    :title="`Wafer Map · ${parameter}`"
    :ui="{ content: 'w-[92vw] sm:max-w-[720px]' }"
  >
    <template #body>
      <div class="flex flex-col items-center gap-3">
        <div class="flex w-full items-center justify-end">
          <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
            <button
              v-for="m in (['Field', 'Die'] as const)"
              :key="m"
              type="button"
              class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
              :class="mode === m ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm' : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="mode = m"
            >{{ m }}</button>
          </div>
          <EbeamSkewvoirWaferMapOptions
            v-model:options="options"
            class="ml-1.5"
          />
        </div>

        <div class="aspect-square w-full max-w-[560px]">
          <EbeamSkewvoirWaferMap
            :rows="rows"
            :parameter="parameter"
            :unit="unit"
            :geo="geo"
            :mode="mode"
            :options="options"
            :color-min="effectiveRange.colorMin"
            :color-max="effectiveRange.colorMax"
            :focused-sequence="focusedSequence"
            :outlier-seqs="outlierSeqs"
            @focus="$emit('focus', $event)"
            @rangechange="autoRange = $event"
          />
        </div>

        <EbeamSkewvoirColorScaleBar
          :min="effectiveRange.colorMin"
          :max="effectiveRange.colorMax"
          :unit="unit"
        />
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { WaferGeometry } from '~/utils/waferGeometry'
import { detailWaferMapOptions, resolveColorRange } from '~/utils/waferMapOptions'

defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  geo: WaferGeometry
  focusedSequence: number | null
  outlierSeqs: number[]
}>()
defineEmits<{ focus: [sequence: number] }>()

const open = defineModel<boolean>('open', { required: true })

// The modal keeps its own option copy (grid on) so the compact panel is never
// affected by tweaks made here.
const mode = ref<'Field' | 'Die'>('Field')
const options = ref(detailWaferMapOptions())
const autoRange = ref<{ min: number, max: number } | null>(null)
const effectiveRange = computed(() => {
  const auto = autoRange.value ?? { min: 0, max: 1 }
  const r = resolveColorRange(options.value.colorMode, options.value.colorMin, options.value.colorMax, auto)
  return { colorMin: r.min, colorMax: r.max }
})
</script>
```

- [ ] **Step 2: Add the enlarge button + modal to the wrapper**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`:

Extend the `#actions` slot (from Task 8) to include an enlarge button before the options gear:

```vue
    <template #actions>
      <UButton
        icon="i-lucide-maximize-2"
        color="neutral"
        variant="ghost"
        size="xs"
        aria-label="확대"
        @click="detailOpen = true"
      />
      <EbeamSkewvoirWaferMapOptions v-model:options="options" />
    </template>
```

Add the modal at the end of the PanelFrame default content (just before `</EbeamSkewvoirPanelFrame>`):

```vue
    <EbeamSkewvoirWaferDetailModal
      v-model:open="detailOpen"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :geo="analysis.waferGeo.value"
      :focused-sequence="analysis.focusedSequence.value"
      :outlier-seqs="outlierSeqs"
      @focus="analysis.setFocusedSequence"
    />
```

Add the open-state ref to `<script setup>`:

```ts
const detailOpen = ref(false)
```

- [ ] **Step 3: Bump the panel wafer square height**

In `app/components/ebeam/skewvoir/dashboard/WaferMap.vue`, widen the wafer square cap (line 22) so the in-panel map is larger while the sibling radius plot keeps `flex-1`:

```vue
        <div class="aspect-square w-full max-w-[22rem]">
```

- [ ] **Step 4: Lint + verify**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -5`
Expected: clean.

Via `verify` skill: an enlarge (⤢) button opens a large modal showing the demo-style wafer map with the die-index grid on by default, its own Field/Die toggle + gear, a big color bar; the compact panel keeps its own (grid-off) state after the modal closes.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferDetailModal.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue
git commit -m "feat(skewvoir): shared wafer detail modal + enlarge affordance"
```

---

## Task 10: Final verification pass

**Files:** none (verification only).

- [ ] **Step 1: Full test + lint sweep**

Run:

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
npm --prefix front-dev-home run lint 2>&1 | tail -5
npm run lint:md 2>&1 | grep "2026-07-16-skewvoir-wafer-map" || echo "md ok"
```

Expected: `# fail 0`; eslint clean; no md issues in this plan or the spec.

- [ ] **Step 2: End-to-end app check (verify skill)**

Confirm on 측정 개요:
- Toggle reads **Field | Die**; Field = dots, Die = tiles.
- Hover shows seq / Field (die) / MP / value; failures show `측정 실패`.
- Gear popover toggles crosshair, die-index grid, MP labels, notch live.
- Manual color range recolors map + bar.
- Color bar shows min/mid/max + unit.
- Enlarge opens the large modal with grid on; panel state unaffected after close.

- [ ] **Step 3: Commit (only if any fixups were needed)**

```bash
git add -A
git commit -m "chore(skewvoir): wafer-map enhancement verification fixups"
```

---

## Self-Review

**Spec coverage:**

- Terminology rename → Task 4. ✓
- Rich tooltip with field info → Tasks 3 + 5. ✓
- Crosshair + die-index grid (both toggleable) → Tasks 2 + 7 + 8. ✓
- Color-scale bar → Task 6. ✓
- MP labels → Task 7. ✓
- Adjustable color range → Tasks 1 + 7 + 8. ✓
- Notch marker → Task 7. ✓
- Shared detail modal + enlarge → Tasks 1 + 9. ✓
- Reusable pieces, no Position Stack changes → ColorScaleBar / WaferMapOptions / WaferDetailModal are standalone; WaferHeatChart untouched. ✓
- Height bump → Task 9 Step 3. ✓
- `node:test` convention (no component tests) → all tests are util-level. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; commands have expected output. ✓

**Type consistency:** `WaferMapOptions` fields match across `waferMapOptions.ts`, leaf props, popover `defineModel`, modal, wrapper. `resolveColorRange` signature identical in Tasks 1/8/9. `formatWaferTooltip` input matches leaf call. `metaBySeq` value shape `{ field, mp, n }` consistent (Task 5 → Task 7 label). Mode union `'Field' | 'Die'` consistent in leaf, wrapper, modal. ✓
