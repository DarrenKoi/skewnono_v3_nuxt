# Skewvoir Selected-Point Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each checkbox-selected measurement point its own color, held constant across the Wafer Map, Radius Plot, Distribution, and the Measurement Points table (legend).

**Architecture:** One deterministic pure helper (`assignSiteColors`) maps the insertion-ordered `selectedSites` keys to a fixed identity palette, mirroring the existing `hardwareCompare.ts` "color = identity" convention. The composable exposes a `siteColor(param, seq)` accessor; each chart wrapper derives an active-parameter `seq → color` map (or `value → color` pairs for the distribution) and hands it to its leaf, which paints its existing selected-overlay per point. Every chart still renders a single parameter — this colors *selected sites*, not multiple parameters.

**Tech Stack:** Nuxt 4 SPA, Vue 3 `<script setup>`, ECharts (canvas), Node's built-in test runner (`node --test`).

## Global Constraints

- Node test runner only: `npm --prefix front-dev-home test` runs `node --test "app/**/*.test.ts"`. Test files are pure-logic `.ts`, imported with an explicit `.ts` extension (see `hardwareCompare.test.ts`).
- Type-check gate: `npm --prefix front-dev-home run typecheck` (`nuxt typecheck`). Lint gate: `npm --prefix front-dev-home run lint` (`eslint .`).
- No Pinia; state is `useState`-backed in `useSkewvoirAnalysis.ts`.
- ECharts cannot read CSS custom properties — colors come from TS constants (`chartPalette.ts`) or the theme palette via `useChartPalette()`.
- Identity colors are a **fixed constant** (like `SK_SCALE`/`SK_STATE`), never theme-driven.
- Cap at the palette length: picks past the cap get **no color entry** and render in the theme's neutral/`muted` tone. Never repeat a hue.
- Selection order is the insertion order of `selectedSites` (`toggleKey` appends). Deselect-reshuffle is accepted; do not add a persistent slot map.
- Single parameter per chart. Do **not** overlay `selectedParams`.
- Work on `main`; commit at the end of each task.

---

### Task 1: Identity palette + pure color helper

**Files:**
- Modify: `front-dev-home/app/utils/chartPalette.ts` (add `SK_SITE` after `SK_STATE`, ~line 29)
- Create: `front-dev-home/app/utils/siteColors.ts`
- Test: `front-dev-home/app/utils/siteColors.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `export const SK_SITE: readonly string[]` (in `chartPalette.ts`)
  - `export function assignSiteColors(orderedSiteKeys: readonly string[], ramp?: readonly string[]): Record<string, string>` (in `siteColors.ts`)

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/siteColors.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { assignSiteColors } from './siteColors.ts'

const RAMP = ['#a', '#b', '#c']

test('assignSiteColors: maps keys to the ramp in insertion order', () => {
  const colors = assignSiteColors(['P 1', 'P 2', 'P 3'], RAMP)
  assert.deepEqual(colors, { 'P 1': '#a', 'P 2': '#b', 'P 3': '#c' })
})

test('assignSiteColors: caps at ramp length — overflow keys get no entry', () => {
  const colors = assignSiteColors(['P 1', 'P 2', 'P 3', 'P 4'], RAMP)
  assert.equal(colors['P 4'], undefined)
  assert.equal(Object.keys(colors).length, 3)
})

test('assignSiteColors: order of keys determines the color', () => {
  const colors = assignSiteColors(['B 5', 'A 2'], RAMP)
  assert.equal(colors['B 5'], '#a')
  assert.equal(colors['A 2'], '#b')
})

test('assignSiteColors: empty input yields an empty map', () => {
  assert.deepEqual(assignSiteColors([], RAMP), {})
})

test('assignSiteColors: defaults to SK_SITE when no ramp is given', () => {
  const colors = assignSiteColors(['P 1'])
  assert.equal(typeof colors['P 1'], 'string')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/siteColors.test.ts`
Expected: FAIL — cannot resolve `./siteColors.ts` (module does not exist yet).

- [ ] **Step 3: Add the `SK_SITE` palette constant**

In `front-dev-home/app/utils/chartPalette.ts`, immediately after the `SK_STATE` block (ends ~line 29), add:

```ts
/**
 * Identity palette for multi-selected measurement points. Like SK_SCALE and
 * SK_STATE this is a FIXED constant, not theme-driven: a selected point's color
 * IS its identity across the wafer map, radius plot, distribution and points
 * table, so it must stay stable across themes and screenshots. Ordered
 * cool-first so the earliest picks sit farthest from the heat ramp's warm end
 * and the semantic red (SK_STATE.bad) — an identity halo must never read as
 * severity. Capped: a selection past this length falls back to a neutral tone.
 */
export const SK_SITE = [
  '#0E7C86', // teal
  '#2F6DB5', // blue
  '#7A5EC4', // violet
  '#3E8E5E', // green
  '#B2568B', // magenta
  '#5B6C8F', // slate
  '#1F9E8F', // sea green
  '#8A6D3F', // brown
  '#C98A2E', // amber
  '#B0413A'  // brick (warm — last slot, only reached with many picks)
] as const
```

- [ ] **Step 4: Write the pure helper**

Create `front-dev-home/app/utils/siteColors.ts`:

```ts
// Pure: deterministic identity-color assignment for multi-selected measurement
// sites, mirroring hardwareCompare.ts. A selected site's color IS its identity
// across the wafer map, radius plot, distribution and points table, so one
// source assigns it. Kept out of the composable so it can be unit-tested under
// node --test. Selection order (the insertion order of the site-key list)
// drives the mapping; keys past the ramp get NO entry — consumers paint those a
// neutral tone. We cap rather than cycle because a repeated hue would be a false
// identity match (two different points sharing a color).
import { SK_SITE } from './chartPalette'

export function assignSiteColors(
  orderedSiteKeys: readonly string[],
  ramp: readonly string[] = SK_SITE
): Record<string, string> {
  const out: Record<string, string> = {}
  orderedSiteKeys.forEach((key, i) => {
    if (i < ramp.length) out[key] = ramp[i]!
  })
  return out
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/siteColors.test.ts`
Expected: PASS — 5 tests, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/chartPalette.ts front-dev-home/app/utils/siteColors.ts front-dev-home/app/utils/siteColors.test.ts
git commit -m "feat(skewvoir): add SK_SITE identity palette + assignSiteColors helper

Deterministic per-site color assignment (mirrors hardwareCompare.ts), keyed by
the insertion-ordered selection list, capped at the palette length.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Expose `siteColor` from the analysis composable

**Files:**
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts` (add derivation after `selectedSeqsForActiveParam`, ~line 295; add to the return object, ~line 605; add imports at top)

**Interfaces:**
- Consumes: `assignSiteColors` (Task 1), `SK_SITE` (Task 1), `selectedSites`, `siteKey`.
- Produces: on the object returned by `useSkewvoirAnalysis()`:
  - `siteColor(param: string, seq: number): string | null` — identity color for a selected site, or `null` when past the palette cap / not selected.

- [ ] **Step 1: Add imports**

At the top of `front-dev-home/app/composables/useSkewvoirAnalysis.ts`, confirm `siteKey` is already imported from `~/utils/mpSelection` (it is used at lines 269/292). Add the two new imports next to the existing util imports:

```ts
import { assignSiteColors } from '~/utils/siteColors'
import { SK_SITE } from '~/utils/chartPalette'
```

(If `chartPalette` is already imported for another symbol, add `SK_SITE` to that existing import instead of a second line.)

- [ ] **Step 2: Add the derivation**

Immediately after the `selectedSeqsForActiveParam` computed (which ends ~line 295), add:

```ts
  // Identity color per selected site — one deterministic source shared by the
  // wafer map, radius plot, distribution and points table (see utils/siteColors).
  // Keyed by the same (param, seq) key as selectedSites; picks past the palette
  // cap return null so each consumer can paint them its own neutral tone.
  const siteColorMap = computed<Record<string, string>>(() =>
    assignSiteColors(selectedSites.value, SK_SITE))
  const siteColor = (param: string, seq: number): string | null =>
    siteColorMap.value[siteKey(param, seq)] ?? null
```

- [ ] **Step 3: Export it**

In the returned object, add `siteColor` right after `selectedSeqsForActiveParam` (~line 605):

```ts
    selectedSeqsForActiveParam,
    siteColor,
```

- [ ] **Step 4: Verify types**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS — no new errors. (If the `SkewvoirAnalysis` type is exported via `ReturnType<typeof ...>`, `siteColor` is now part of it automatically.)

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useSkewvoirAnalysis.ts
git commit -m "feat(skewvoir): expose siteColor(param, seq) from analysis composable

One shared identity-color source for the selection, derived from selectedSites.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Per-point color on the Wafer Map (leaf + wrapper + detail modal)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue` (leaf: props ~line 19-40, `selectedPoints` ~line 84-89, selected series ~line 253-255)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue` (wrapper: add `seqColors` computed, pass to leaf + detail modal)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/WaferDetailModal.vue` (add `seqColors` prop, forward to leaf)

**Interfaces:**
- Consumes: `analysis.siteColor` (Task 2), `analysis.selectedSeqsForActiveParam`, `useChartPalette()`.
- Produces: leaf prop `seqColors?: Record<number, string>` (default `{}`), forwarded by the wrapper and modal.

- [ ] **Step 1: Add the `seqColors` prop to the leaf**

In `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue`, add to the props interface (after `selectedSeqs?`, ~line 27):

```ts
  /** Per-sequence identity color for the multi-selection (active param). A seq
   *  absent from this map falls back to the shared brand halo. */
  seqColors?: Record<number, string>
```

And to the `withDefaults` defaults (after `selectedSeqs: () => [],`, ~line 35):

```ts
  seqColors: () => ({}),
```

- [ ] **Step 2: Color each selected point in `selectedPoints`**

Replace the `selectedPoints` computed (~line 84-89) with:

```ts
// Halo on any active point whose sequence is in the multi-selection set, colored
// by that point's identity color (falling back to the shared brand halo).
const selectedPoints = computed(() => {
  const picked = new Set(props.selectedSeqs)
  return activePoints.value
    .filter(p => p.seqs.some(s => picked.has(s)))
    .map((p) => {
      const hitSeq = p.seqs.find(s => picked.has(s)) ?? p.seq
      const color = props.seqColors[hitSeq] ?? sk.value.brand
      return { name: String(p.seq), value: [p.x, p.y], itemStyle: { color, borderColor: color } }
    })
})
```

- [ ] **Step 3: Let the per-item color show through the selected series**

In the selected-halo series (~line 253-255), drop the hardcoded `color`/`borderColor` (they now come per-item) but keep the opacity + border width:

```ts
    { type: 'scatter', symbol: 'circle', symbolSize: 22, data: selectedPoints.value,
      itemStyle: { opacity: 0.18, borderWidth: 1.5 },
      silent: true, z: 3 },
```

- [ ] **Step 4: Derive `seqColors` in the dashboard wrapper**

In `front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue` `<script setup>`, add a palette handle and the map (after `const options = ...`, ~line 99):

```ts
const sk = useChartPalette()

// Active-parameter selected sequences → identity color, with the neutral muted
// tone for any pick past the palette cap. Fed to both the inline map and modal.
const seqColors = computed<Record<number, string>>(() => {
  const param = props.analysis.activeParam.value
  const out: Record<number, string> = {}
  for (const seq of props.analysis.selectedSeqsForActiveParam.value) {
    out[seq] = props.analysis.siteColor(param, seq) ?? sk.value.muted
  }
  return out
})
```

- [ ] **Step 5: Pass `seqColors` to the leaf and the detail modal**

In the same file's template, add `:seq-colors="seqColors"` to `<EbeamSkewvoirWaferMap>` (after `:selected-seqs=...`, ~line 49) and to `<EbeamSkewvoirWaferDetailModal>` (after `:selected-seqs=...`, ~line 84).

- [ ] **Step 6: Thread `seqColors` through the detail modal**

In `front-dev-home/app/components/ebeam/skewvoir/WaferDetailModal.vue`, add to `defineProps` (after `selectedSeqs?`, ~line 68):

```ts
  seqColors?: Record<number, string>
```

And in its template, add `:seq-colors="seqColors"` to the `<EbeamSkewvoirWaferMap>` (after `:selected-seqs="selectedSeqs"`, ~line 40).

- [ ] **Step 7: Verify types + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS — no new errors.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/WaferDetailModal.vue
git commit -m "feat(skewvoir): color wafer-map selected halos per point

Each selected site's halo takes its identity color instead of one shared brand;
overflow picks use the muted tone. Threaded through the detail modal too.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Per-point color on the Radius Plot (leaf + wrapper)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue` (leaf: props ~line 14-30, `selectedPts` ~line 72-75, selected series ~line 270-279)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue` (wrapper: add `seqColors` computed, pass to leaf)

**Interfaces:**
- Consumes: `analysis.siteColor`, `analysis.selectedSeqsForActiveParam`, `useChartPalette()`.
- Produces: leaf prop `seqColors?: Record<number, string>` (default `{}`).

- [ ] **Step 1: Add the `seqColors` prop to the leaf**

In `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue`, add to the props interface (after `selectedSeqs?`, ~line 19):

```ts
  seqColors?: Record<number, string>
```

And to the defaults (after `selectedSeqs: () => [],`, ~line 26):

```ts
  seqColors: () => ({}),
```

- [ ] **Step 2: Color each selected point in `selectedPts`**

Replace the `selectedPts` computed (~line 72-75) with:

```ts
const selectedPts = computed(() => {
  const picked = new Set(props.selectedSeqs)
  return scatterData.value
    .filter(point => picked.has(Number(point.name)))
    .map((point) => {
      const color = props.seqColors[Number(point.name)] ?? sk.value.series
      return { ...point, itemStyle: { color, borderColor: color } }
    })
})
```

- [ ] **Step 3: Let the per-item color show through the selected series**

In the `name: 'selected'` series (~line 270-279), drop the hardcoded `color`/`borderColor`, keep opacity + border width:

```ts
      {
        name: 'selected',
        type: 'scatter',
        symbolSize: 18,
        data: selectedPts.value,
        itemStyle: { opacity: 0.18, borderWidth: 1.5 },
        tooltip: { show: false },
        silent: true,
        z: 5
      },
```

- [ ] **Step 4: Derive + pass `seqColors` in the wrapper**

In `front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue` `<script setup>`, add (after `const model = ...`, ~line 79):

```ts
const sk = useChartPalette()

const seqColors = computed<Record<number, string>>(() => {
  const param = props.analysis.activeParam.value
  const out: Record<number, string> = {}
  for (const seq of props.analysis.selectedSeqsForActiveParam.value) {
    out[seq] = props.analysis.siteColor(param, seq) ?? sk.value.muted
  }
  return out
})
```

In the template, add `:seq-colors="seqColors"` to `<EbeamSkewvoirRadiusChart>` (after `:selected-seqs=...`, ~line 43).

- [ ] **Step 5: Verify types + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue
git commit -m "feat(skewvoir): color radius-plot selected points per point

Selected radial points take their identity color (was one shared series color),
matching the wafer map; overflow picks use the muted tone.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Highlight selected points in the Distribution (leaf + wrapper)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue` (leaf: add `highlights` prop; extend `bins`; Hist bin tint; Box overlay; Violin rug)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/Distribution.vue` (wrapper: compute + pass `highlights`)

**Interfaces:**
- Consumes: `analysis.siteColor`, `analysis.selectedSeqsForActiveParam`, `analysis.siteRows`, `analysis.activeParam`, `useChartPalette()`, `isMeasuredRow`.
- Produces: leaf prop `highlights?: { value: number, color: string }[]` (default `[]`).

Scope: **Box + Violin** get true per-point marks; **Hist** tints the containing bin. ECDF is not used on the dashboard and is left unchanged.

- [ ] **Step 1: Add the `highlights` prop**

In `front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue`, add to the props interface (after `heightClass?`, ~line 44) and its defaults (~line 45-48):

```ts
  // Selected points to mark, each with its identity color (active param only).
  // Box: colored raw dots; Violin: value-axis rug; Hist: tinted containing bin.
  highlights?: { value: number, color: string }[]
```

```ts
  heightClass: 'h-72',
  highlights: () => []
```

- [ ] **Step 2: Expose `min` + `width` from `bins` (DRY — reused by Hist tint)**

Replace the `bins` computed's `return` (~line 92-93) so the bin geometry is shared:

```ts
  const centers = counts.map((_, i) => min + width * (i + 0.5))
  return { centers, counts, min, width }
```

(The early-empty return becomes `return { centers: [] as number[], counts: [] as number[], min: 0, width: 1 }`.)

- [ ] **Step 3: Tint the Hist bins that contain a selected value**

Add a helper computed (near `bins`, after it):

```ts
// Bin index → identity color for any bin holding a selected value (first wins).
const histHighlightBins = computed<Map<number, string>>(() => {
  const map = new Map<number, string>()
  const { counts, min, width } = bins.value
  if (!counts.length || !props.highlights.length) return map
  for (const h of props.highlights) {
    const idx = Math.min(BIN_COUNT - 1, Math.max(0, Math.floor((h.value - min) / width)))
    if (!map.has(idx)) map.set(idx, h.color)
  }
  return map
})
```

In `histOption` (~line 133-138), replace the bar series `data` so highlighted bins carry a per-item color:

```ts
  series: [{
    type: 'bar',
    data: bins.value.counts.map((c, i) => {
      const color = histHighlightBins.value.get(i)
      return color ? { value: c, itemStyle: { color, borderRadius: [2, 2, 0, 0] } } : c
    }),
    barWidth: '90%',
    itemStyle: { color: sk.value.seriesSoft, borderRadius: [2, 2, 0, 0] }
  }]
```

- [ ] **Step 4: Overlay colored dots in Box mode**

In `boxOption` (~line 180-215), add a highlight overlay series. Just before the `return {`, compute the overlay points (deterministic jitter around the single category at x=0):

```ts
  const highlightPts = props.highlights.map((h, i) => ({
    value: [(jitterHash(1, i) - 0.5) * 0.3, h.value],
    itemStyle: { color: h.color }
  }))
```

Then append to the `series` array (after the existing `scatter` raw-points series):

```ts
      ...(highlightPts.length
        ? [{
            type: 'scatter' as const,
            symbolSize: 9,
            data: highlightPts,
            z: 3,
            tooltip: { show: false }
          }]
        : [])
```

- [ ] **Step 5: Add a colored rug in Violin mode**

In `violinOption` (~line 219-242), compute rug ticks along the bottom of the value axis (below the mirrored density). Just before the `return {`:

```ts
  const rugY = -Math.max(1, ...counts) / 2 * 1.12
  const rugPts = props.highlights.map(h => ({
    value: [h.value, rugY],
    itemStyle: { color: h.color }
  }))
```

Then append to the `series` array (after the two density line series):

```ts
      ...(rugPts.length
        ? [{
            type: 'scatter' as const,
            symbol: 'rect',
            symbolSize: [2, 10],
            data: rugPts,
            silent: true,
            z: 3,
            tooltip: { show: false }
          }]
        : [])
```

- [ ] **Step 6: Compute + pass `highlights` from the wrapper**

In `front-dev-home/app/components/ebeam/skewvoir/dashboard/Distribution.vue` `<script setup>`, add:

```ts
const sk = useChartPalette()

// Selected points of the active parameter as (value, identity color) pairs;
// overflow picks use the muted tone. The chart marks them per its active shape.
const highlights = computed<{ value: number, color: string }[]>(() => {
  const param = props.analysis.activeParam.value
  const picked = new Set(props.analysis.selectedSeqsForActiveParam.value)
  const out: { value: number, color: string }[] = []
  for (const r of props.analysis.siteRows.value) {
    if (r.parameter !== param || !picked.has(r.sequence)) continue
    if (!isMeasuredRow(r) || r.cd_value == null) continue
    out.push({ value: r.cd_value, color: props.analysis.siteColor(param, r.sequence) ?? sk.value.muted })
  }
  return out
})
```

In the template, add `:highlights="highlights"` to `<EbeamSkewvoirDistributionChart>` (after `:mode="mode"`, ~line 25).

- [ ] **Step 7: Verify types + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 8: Run the full unit suite (nothing regressed)**

Run: `npm --prefix front-dev-home test`
Expected: PASS — all existing tests plus Task 1's `siteColors` tests.

- [ ] **Step 9: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/Distribution.vue
git commit -m "feat(skewvoir): mark selected points in the distribution

Box: colored raw dots; Violin: value-axis rug; Hist: tint the containing bin.
Each uses the point's identity color; overflow picks use the muted tone.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Color swatch legend in the Measurement Points table

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue` (checkbox cell ~line 123-133; add `swatchColor` helper in `<script setup>`)

**Interfaces:**
- Consumes: `analysis.siteColor`.
- Produces: nothing (visual only).

- [ ] **Step 1: Add the swatch-color helper**

In `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue` `<script setup>`, near `keyOf`/`selectedSet` (~line 323), add:

```ts
// Legend swatch color for a selected row = its identity color across the charts;
// a pick past the palette cap has no color and shows the neutral CSS token.
const swatchColor = (p: Point): string =>
  props.analysis.siteColor(p.param, p.seq) ?? 'var(--sk-ink-subtle)'
```

- [ ] **Step 2: Render the swatch in the checkbox cell**

In the checkbox `<td>` (~line 123-133), add a swatch before the `<UCheckbox>`, visible only for selected rows:

```html
            <td
              class="px-1.5 py-1.5 text-center whitespace-nowrap"
              @click.stop
            >
              <span
                v-if="selectedSet.has(keyOf(p))"
                class="mr-1 inline-block h-2.5 w-2.5 rounded-full align-middle"
                :style="{ backgroundColor: swatchColor(p) }"
                aria-hidden="true"
              />
              <UCheckbox
                size="xs"
                :aria-label="`측정점 ${p.seq} 선택`"
                :model-value="selectedSet.has(keyOf(p))"
                @update:model-value="onCheckboxToggle(p)"
              />
            </td>
```

- [ ] **Step 3: Verify types + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue
git commit -m "feat(skewvoir): show identity-color swatch per selected points row

The points table becomes the legend mapping each color to its measurement point.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Manual visual verification

**Files:** none (verification only).

- [ ] **Step 1: Launch the app**

Use the `verify` skill (Flask mock + Nuxt SPA). Navigate to a skewvoir analysis dashboard (e.g. `/ebeam/cd-sem/skewvoir/analysis` with a focus MSR that has measured sites).

- [ ] **Step 2: Confirm the feature end-to-end**

Check each acceptance criterion:
- Select 3–4 measurement points via the table checkboxes. Each gets a distinct swatch color in the table.
- The **same** hue identifies each point in the Wafer Map halo, the Radius Plot dot, and the Distribution (toggle **Box** → colored raw dots; **Violin** → colored rug ticks; **Hist** → the containing bin is tinted).
- Switch the active parameter (파라미터 요약): only that parameter's selected sites light up; colors stay consistent per point.
- Exceed ~10 selected points: extra picks render in the neutral/muted tone everywhere (no repeated hues).
- Toggle light/dark color mode: swatches and halos stay legible.

- [ ] **Step 3: Note any visual issues** for follow-up (e.g. halo opacity too faint against the heat map). Record, do not fix here — the plan's functional scope is complete.

---

## Self-Review

**Spec coverage:**
- Single deterministic color source → Task 1 (`assignSiteColors`) + Task 2 (`siteColor`). ✓
- Fixed cool-first palette, cap→neutral → Task 1 (`SK_SITE`), consumers' `?? muted`. ✓
- Wafer Map per-point → Task 3 (leaf + wrapper + detail modal). ✓
- Radius Plot per-point → Task 4. ✓
- Distribution Box+Violin marks, Hist bin tint → Task 5. ✓
- Table legend swatch → Task 6. ✓
- Single parameter per chart (no multi-param overlay) → preserved; wrappers only ever pass active-param seqs/values. ✓
- Edge cases (overflow→muted, cross-param via global key, deselect reshuffle) → covered by the pure helper + `?? muted` fallback in every wrapper. ✓

**Type consistency:** `seqColors: Record<number, string>` is the leaf-prop name in Tasks 3 and 4; `highlights: { value, color }[]` is the leaf-prop name in Task 5; `siteColor(param, seq): string | null` is defined in Task 2 and consumed unchanged in Tasks 3–6. Consistent.

**Placeholder scan:** No TBD/TODO; every code step shows full code. Exact hex values in `SK_SITE` are tunable but concrete.
