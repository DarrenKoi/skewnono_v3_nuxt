# Skewvoir CD Outlier Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag MSRs whose CD mean or spread is a statistical outlier (median+MAD modified z-score) and recolor/enlarge those points in the skewvoir 시계열 추이 chart.

**Architecture:** A framework-free pure util (`madOutliers.ts`) computes per-point boolean flags from a numeric array. `AnalyzePanel`'s `timeSeriesPoints` computed runs it over the selection's means and stds, attaching an `outlier` flag to each `TimeSeriesPoint`. `TimeSeriesChart` reads that flag to style the `mean` series per-datum (color + symbol size) and adds one tooltip line. Detection is relative to the current selection, so it stays in the frontend.

**Tech Stack:** Nuxt 4 (Vue 3, `<script setup lang="ts">`), ECharts 6 (via `useEchart`), Node built-in test runner (`node --test`).

## Global Constraints

- Test runner: `node --test "app/**/*.test.ts"` (run via `npm --prefix front-dev-home test`). Tests use `node:test` + `node:assert/strict`, import local modules with explicit `.ts` extension.
- Pure utils live in `front-dev-home/app/utils/`, framework-free, colocated `*.test.ts` (mirror `outlierDetect.ts` / `mdcMatrix.ts`).
- Modified z-score constant: `0.6745`. Default threshold `k = 3.5`, default `minN = 5`.
- Outlier point colors: mean → `#dc2626` (red, size 10); spread-only → `#d97706` (amber, size 9); normal → `#2563eb` (blue, size 6). Mean takes priority when both flag.
- Commit only the files each task touches. Run `npm run lint:md` (repo root) after editing any `.md`.

---

### Task 1: `detectMadOutliers` pure util

**Files:**
- Create: `front-dev-home/app/utils/madOutliers.ts`
- Test: `front-dev-home/app/utils/madOutliers.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `detectMadOutliers(values: number[], k?: number, minN?: number): boolean[]` — returns a boolean array the same length as `values`; `true` marks an outlier. Defaults `k = 3.5`, `minN = 5`. Also exports `MAD_DEFAULT_K = 3.5` and `MAD_DEFAULT_MIN_N = 5`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/madOutliers.test.ts`:

```ts
// Pure-logic tests for madOutliers. Run: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectMadOutliers, MAD_DEFAULT_K, MAD_DEFAULT_MIN_N } from './madOutliers.ts'

test('empty array → empty result', () => {
  assert.deepEqual(detectMadOutliers([]), [])
})

test('below minN → all false (length preserved)', () => {
  assert.deepEqual(detectMadOutliers([1, 2, 100, 3]), [false, false, false, false])
})

test('clean series at/above minN → no outliers', () => {
  assert.deepEqual(
    detectMadOutliers([10, 11, 9, 10, 12, 8]),
    [false, false, false, false, false, false]
  )
})

test('single clear outlier is flagged, others are not', () => {
  const flags = detectMadOutliers([10, 10, 11, 9, 10, 80])
  assert.deepEqual(flags, [false, false, false, false, false, true])
})

test('all-identical values (MAD=0) → no false positives', () => {
  assert.deepEqual(detectMadOutliers([7, 7, 7, 7, 7]), [false, false, false, false, false])
})

test('MAD=0 with one different value → only the different one flags', () => {
  // median 7, MAD 0 → fall back to "differs from median".
  const flags = detectMadOutliers([7, 7, 7, 7, 7, 9])
  assert.deepEqual(flags, [false, false, false, false, false, true])
})

test('masking: a single extreme does not hide itself (vs classic z-score)', () => {
  // Tight cluster + one far value; classic mean±std would inflate std and miss it.
  const flags = detectMadOutliers([50, 51, 49, 50, 52, 48, 500])
  assert.equal(flags[6], true)
  assert.equal(flags.slice(0, 6).some(Boolean), false)
})

test('k is configurable (looser k flags fewer)', () => {
  const values = [10, 10, 11, 9, 10, 20]
  const strict = detectMadOutliers(values, 3.5)
  const loose = detectMadOutliers(values, 100)
  assert.equal(strict[5], true)
  assert.equal(loose.some(Boolean), false)
})

test('exported defaults', () => {
  assert.equal(MAD_DEFAULT_K, 3.5)
  assert.equal(MAD_DEFAULT_MIN_N, 5)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — cannot find module `./madOutliers.ts` / `detectMadOutliers is not a function`.

- [ ] **Step 3: Write minimal implementation**

Create `front-dev-home/app/utils/madOutliers.ts`:

```ts
// Robust outlier detection via median + MAD (modified z-score).
// Resistant to a few extreme values masking themselves the way classic
// mean±std does, which matters for the small MSR selections on skewvoir.
// Pure + framework-free (mirrors outlierDetect.ts), unit-tested with node --test.

export const MAD_DEFAULT_K = 3.5
export const MAD_DEFAULT_MIN_N = 5

// 0.6745 = 0.75 quantile of the standard normal; scales MAD so the
// modified z-score is comparable to a standard z-score for normal data.
const MAD_SCALE = 0.6745

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

export const detectMadOutliers = (
  values: number[],
  k: number = MAD_DEFAULT_K,
  minN: number = MAD_DEFAULT_MIN_N
): boolean[] => {
  if (values.length < minN) return values.map(() => false)

  const med = median(values)
  const mad = median(values.map(v => Math.abs(v - med)))

  // MAD = 0 means ≥half the values equal the median; dividing would be NaN/Inf.
  // Fall back to flagging only values that differ from the median, so a
  // constant series flags nothing.
  if (mad === 0) return values.map(v => v !== med)

  return values.map(v => Math.abs((MAD_SCALE * (v - med)) / mad) > k)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix front-dev-home test`
Expected: PASS — all `madOutliers` tests green (other suites unaffected).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/madOutliers.ts front-dev-home/app/utils/madOutliers.test.ts
git commit -m "feat(skewvoir): add MAD-based outlier detection util"
```

---

### Task 2: `TimeSeriesChart` per-point outlier styling

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/TimeSeriesChart.vue`

**Interfaces:**
- Consumes: `TimeSeriesPoint[]` via props (existing).
- Produces: extended exported `TimeSeriesPoint` interface with optional `outlier?: { mean: boolean, spread: boolean }`. The `mean` series styles each datum from this flag; the tooltip gains one line when a point is flagged.

- [ ] **Step 1: Extend the `TimeSeriesPoint` interface**

In `front-dev-home/app/components/ebeam/skewvoir/TimeSeriesChart.vue`, add the optional field to the interface:

```ts
export interface TimeSeriesPoint {
  msr: string
  label: string
  eqpId: string
  mean: number
  min: number
  max: number
  std: number
  // Set by AnalyzePanel from detectMadOutliers; absent ⇒ treated as not-outlier.
  outlier?: { mean: boolean, spread: boolean }
}
```

- [ ] **Step 2: Build per-datum styled mean data**

Replace the existing `means` computed (`const means = computed(() => props.points.map(p => p.mean))`) with a per-datum object array so ECharts can style each point individually:

```ts
// Per-datum styling so flagged points stand out without a second series.
// mean outlier → red+large; spread-only → amber+medium; normal → blue.
const meanData = computed(() =>
  props.points.map((p) => {
    const isMean = p.outlier?.mean ?? false
    const isSpread = p.outlier?.spread ?? false
    const color = isMean ? '#dc2626' : isSpread ? '#d97706' : '#2563eb'
    const symbolSize = isMean ? 10 : isSpread ? 9 : 6
    return { value: p.mean, itemStyle: { color }, symbolSize }
  })
)
```

- [ ] **Step 3: Point the mean series at the new data**

In the `series` array, change the `mean` series `data` from `means.value` to `meanData.value`. Leave its `lineStyle`/`itemStyle` defaults (they color the connecting line `#2563eb`; per-point `itemStyle` overrides the marker). The series object becomes:

```ts
{
  name: 'mean',
  type: 'line',
  data: meanData.value,
  smooth: false,
  showSymbol: true,
  symbolSize: 6,
  lineStyle: { width: 2, color: '#2563eb' },
  itemStyle: { color: '#2563eb' },
  z: 3
}
```

- [ ] **Step 4: Add the tooltip outlier line**

In the `tooltip.formatter`, after the existing `std` line, append a flag line when the point is an outlier. Replace the return block:

```ts
      const lines = [
        p.label,
        `eqp: ${p.eqpId}`,
        `mean: <b>${p.mean}</b> ${props.unit}`,
        `min/max: ${p.min} / ${p.max}`,
        `std: ${p.std}`
      ]
      const o = p.outlier
      if (o && (o.mean || o.spread)) {
        const kind = o.mean && o.spread ? 'mean+spread' : o.mean ? 'mean' : 'spread'
        lines.push(`<span style="color:#dc2626">⚠ outlier: ${kind}</span>`)
      }
      return lines.join('<br/>')
```

- [ ] **Step 5: Typecheck**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS — no type errors from the edited component (the optional field and `meanData` resolve cleanly).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/TimeSeriesChart.vue
git commit -m "feat(skewvoir): style CD outlier points in time-series chart"
```

---

### Task 3: Wire detection into `AnalyzePanel`

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/AnalyzePanel.vue`

**Interfaces:**
- Consumes: `detectMadOutliers` from Task 1; the extended `TimeSeriesPoint` from Task 2.
- Produces: `timeSeriesPoints` now carries `outlier` per point.

- [ ] **Step 1: Import the util**

In the `<script setup>` of `front-dev-home/app/components/ebeam/skewvoir/AnalyzePanel.vue`, add near the other imports:

```ts
import { detectMadOutliers } from '~/utils/madOutliers'
```

- [ ] **Step 2: Compute flags and attach to each point**

Replace the existing `timeSeriesPoints` computed (currently builds, sorts, and strips `ts`) with the version below. It builds the sorted point list, runs `detectMadOutliers` over the means and stds, then attaches the flags:

```ts
const timeSeriesPoints = computed<TimeSeriesPoint[]>(() => {
  const points: (TimeSeriesPoint & { ts: number })[] = []
  for (const row of props.selectedRows) {
    const file = files.value.get(row.msr)
    const summary = file?.parameters.find(p => p.parameter === selectedParam.value)
    if (!summary) continue
    points.push({
      ts: new Date(row.timestamp).getTime(),
      msr: row.msr,
      label: formatRecipeTimestamp(row.timestamp),
      eqpId: row.eqp_id,
      mean: summary.mean,
      min: summary.min,
      max: summary.max,
      std: summary.std
    })
  }
  points.sort((a, b) => a.ts - b.ts)

  // Outlier flags are relative to this selection: median+MAD over the
  // selection's means (level shift) and stds (spread instability).
  const meanFlags = detectMadOutliers(points.map(p => p.mean))
  const spreadFlags = detectMadOutliers(points.map(p => p.std))

  return points.map(({ ts: _ts, ...rest }, i) => ({
    ...rest,
    outlier: { mean: meanFlags[i] ?? false, spread: spreadFlags[i] ?? false }
  }))
})
```

- [ ] **Step 3: Typecheck**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS — `outlier` matches the extended `TimeSeriesPoint`.

- [ ] **Step 4: Manual smoke check (dev server)**

Run: `npm --prefix front-dev-home run dev` (with Flask mock on :5000). Navigate to `/ebeam/cd-sem/skewvoir`, pick ≥5 MSRs sharing a parameter, and confirm: outlier means render red+large, spread-only render amber, hovering shows the `⚠ outlier:` line, and a selection of <5 MSRs shows no flagged points.

- [ ] **Step 5: Run the full unit suite**

Run: `npm --prefix front-dev-home test`
Expected: PASS — all suites including `madOutliers`.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/AnalyzePanel.vue
git commit -m "feat(skewvoir): flag CD mean/spread outliers in time-series"
```

---

## Self-Review

**Spec coverage:**

- §3 method (median+MAD, k=3.5, minN=5, MAD=0 fallback) → Task 1. ✓
- §4.1 `detectMadOutliers` signature → Task 1. ✓
- §4.2 AnalyzePanel wiring (means + stds, attach `outlier`) → Task 3. ✓
- §4.3 chart interface field, per-datum red/amber/blue + sizes, tooltip line → Task 2. ✓
- §6 edge cases (<5, all-equal, masking) → Task 1 tests + Task 3 smoke. ✓
- §7 tests (empty, below-minN, clean, single, MAD=0, masking) → Task 1. ✓

**Placeholder scan:** none — every code step shows full content.

**Type consistency:** `detectMadOutliers(values, k?, minN?): boolean[]` used identically in Task 1/3; `outlier?: { mean, spread }` defined in Task 2, produced in Task 3, read in Task 2's chart styling. ✓
