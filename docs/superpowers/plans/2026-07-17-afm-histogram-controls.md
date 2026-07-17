# AFM Histogram Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curated controls to the AFM Z-value histogram — bin method (Auto/Custom), display mode (Frequency/Density/Cumulative), normal-curve overlay, percentile marklines, and extended numeric stats.

**Architecture:** Pure histogram math (bin count, binning per mode, extended stats, normal curve sampled at bin centers, quantile→bin index) goes in a new `utils/afmHistogram.ts` unit-tested with `node --test`; `HistogramChart.vue` gains `USelect`/`UInput`/`UCheckbox` controls and wires the util into its `useEchart` option — staying on the existing **category** X axis so the overlay/marklines need no axis rewrite.

**Tech Stack:** Nuxt 4 + NuxtUI v4.6.1 (`USelect`, `UInput`, `UCheckbox`), ECharts (`useEchart`), TypeScript, Node's built-in test runner.

## Global Constraints

- Frontend root `front-dev-home/`; run `npm` there. Tests: `node --test app/utils/afmHistogram.test.ts`. Gates: `npm run typecheck`, `npm run lint`.
- `stdev` is population std (÷N). `kurtosis` is EXCESS kurtosis (normal ⇒ 0). Guards: skewness 0 when N<3 or stdev 0; kurtosis 0 when N<4 or stdev 0; CV 0 when mean 0.
- Bin count is always clamped to [5, 200]; non-finite/degenerate → 5. Custom default 30.
- Degenerate data never throws: empty → single zero bin; zero span (all-equal Z) → single bin holding all N; normal overlay empty when stdev 0.
- Chart stays on a `category` X axis of formatted bin-center labels (as today). The normal overlay is a line series sampled at the bin centers; percentile marklines snap to the bin index containing each quantile.
- `exportName` prop preserved and passed to `useEchart` (keeps PNG hover-download working).
- Pure util: no DOM/Nuxt runtime imports. The `.vue` relies on Nuxt auto-import for util runtime exports; `import type` for its types.
- Work on `main`; commit per task; do NOT push. Tree has UNRELATED concurrent user WIP (`.remember/`, `docs/` deletions, a "chat" feature). Each task `git add`s ONLY its explicit files — never `git add -A`/`git add .`/`git stash`.
- Every commit message ends with:

  ```text
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NHWMRqfxSYaLcagApFG1tB
  ```

---

### Task 1: Pure histogram logic (`utils/afmHistogram.ts`)

**Files:**
- Create: `front-dev-home/app/utils/afmHistogram.ts`
- Test: `front-dev-home/app/utils/afmHistogram.test.ts`

**Interfaces:**
- Produces: `BinMethod`, `HistogramMode`, `HistogramStats`, `HistogramBins`, `histogramStats(zs)`, `resolveBinCount(zs, method, customCount)`, `computeHistogram(zs, binCount, mode)`, `normalCurveOverCenters(stats, mode, binWidth, centers)`, `binIndexForValue(edges, value)`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/afmHistogram.test.ts`:

```ts
// Pure-logic tests for afmHistogram. Run: node --test app/utils/afmHistogram.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  histogramStats,
  resolveBinCount,
  computeHistogram,
  normalCurveOverCenters,
  binIndexForValue
} from './afmHistogram.ts'

const approx = (a: number, b: number, eps = 1e-6) =>
  assert.ok(Math.abs(a - b) <= eps, `${a} ≈ ${b}`)

test('histogramStats: symmetric set', () => {
  const s = histogramStats([1, 2, 3, 4, 5])
  approx(s.mean, 3)
  approx(s.stdev, Math.sqrt(2))
  approx(s.q1, 2)
  approx(s.median, 3)
  approx(s.q3, 4)
  assert.equal(s.min, 1)
  assert.equal(s.max, 5)
  approx(s.skewness, 0)
  approx(s.cv, (Math.sqrt(2) / 3) * 100)
})

test('histogramStats: right-skewed → positive skewness', () => {
  assert.ok(histogramStats([1, 1, 1, 2, 10]).skewness > 0)
})

test('histogramStats: guards (N<3 skew 0, N<4 kurt 0, mean 0 cv 0, empty zeros)', () => {
  assert.equal(histogramStats([1, 2]).skewness, 0)
  assert.equal(histogramStats([1, 2, 3]).kurtosis, 0)
  assert.equal(histogramStats([-1, 1]).cv, 0)
  assert.deepEqual(histogramStats([]).count, 0)
})

test('resolveBinCount: custom clamps to [5,200]', () => {
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', 500), 200)
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', 2), 5)
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', NaN), 5)
})

test('resolveBinCount: auto Sturges for outlier-free data', () => {
  const uniform = Array.from({ length: 100 }, (_, i) => i)
  // Sturges = ceil(1 + log2(100)) = 8; uniform has no >3σ outliers → Sturges.
  assert.equal(resolveBinCount(uniform, 'auto', 30), 8)
})

test('resolveBinCount: empty → 5', () => {
  assert.equal(resolveBinCount([], 'auto', 30), 5)
})

test('computeHistogram: frequency counts sum to N', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'frequency')
  assert.equal(h.values.reduce((a, b) => a + b, 0), 10)
  assert.equal(h.centers.length, 5)
  assert.equal(h.edges.length, 6)
})

test('computeHistogram: density integrates to ~1', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'density')
  const integral = h.values.reduce((a, v) => a + v * h.binWidth, 0)
  approx(integral, 1, 1e-9)
})

test('computeHistogram: cumulative is monotonic ending at N', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'cumulative')
  for (let i = 1; i < h.values.length; i++) assert.ok(h.values[i]! >= h.values[i - 1]!)
  assert.equal(h.values[h.values.length - 1], 10)
})

test('computeHistogram: zero span → single bin holding all', () => {
  const h = computeHistogram([5, 5, 5], 4, 'frequency')
  assert.deepEqual(h.centers, [5])
  assert.deepEqual(h.values, [3])
})

test('computeHistogram: empty → single zero bin', () => {
  const h = computeHistogram([], 5, 'frequency')
  assert.equal(h.values.length, 1)
  assert.equal(h.values[0], 0)
})

test('normalCurveOverCenters: empty when stdev 0, else one y per center peaking near mean', () => {
  const flat = histogramStats([5, 5, 5, 5])
  assert.deepEqual(normalCurveOverCenters(flat, 'density', 1, [5]), [])
  const s = histogramStats([1, 2, 3, 4, 5])
  const centers = [1, 2, 3, 4, 5]
  const ys = normalCurveOverCenters(s, 'density', 1, centers)
  assert.equal(ys.length, 5)
  const peak = ys.indexOf(Math.max(...ys))
  assert.equal(centers[peak], 3) // peak at the mean
})

test('binIndexForValue: locates the containing bin, clamps out-of-range', () => {
  const edges = [0, 2, 4, 6] // bins [0,2),[2,4),[4,6]
  assert.equal(binIndexForValue(edges, 1), 0)
  assert.equal(binIndexForValue(edges, 3), 1)
  assert.equal(binIndexForValue(edges, 6), 2)
  assert.equal(binIndexForValue(edges, -5), 0)
  assert.equal(binIndexForValue(edges, 99), 2)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/afmHistogram.test.ts`
Expected: FAIL — `Cannot find module './afmHistogram.ts'`.

- [ ] **Step 3: Write `afmHistogram.ts`**

Create `front-dev-home/app/utils/afmHistogram.ts`:

```ts
// Pure histogram helpers for the AFM Z-value distribution. No DOM/Nuxt imports
// so they run under `node --test`; HistogramChart.vue wires them into useEchart.

export type BinMethod = 'auto' | 'custom'
export type HistogramMode = 'frequency' | 'density' | 'cumulative'

export interface HistogramStats {
  count: number
  mean: number
  stdev: number
  min: number
  max: number
  q1: number
  median: number
  q3: number
  skewness: number
  kurtosis: number
  cv: number
}

export interface HistogramBins {
  centers: number[]
  values: number[]
  binWidth: number
  edges: number[]
}

const clampBins = (n: number): number =>
  !Number.isFinite(n) ? 5 : Math.max(5, Math.min(200, Math.round(n)))

const meanOf = (nums: number[]): number =>
  nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0

const populationStd = (nums: number[], mu: number): number => {
  if (nums.length < 2) return 0
  return Math.sqrt(nums.reduce((a, b) => a + (b - mu) ** 2, 0) / nums.length)
}

// Linear-interpolated quantile on an ascending-sorted array; p in [0, 1].
const quantile = (sortedAsc: number[], p: number): number => {
  if (sortedAsc.length === 0) return 0
  if (sortedAsc.length === 1) return sortedAsc[0]!
  const pos = (sortedAsc.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sortedAsc[lo]! + (sortedAsc[hi]! - sortedAsc[lo]!) * (pos - lo)
}

// Abramowitz-Stegun erf approximation (max error ~1.5e-7).
const erf = (x: number): number => {
  const sign = x < 0 ? -1 : 1
  const ax = Math.abs(x)
  const t = 1 / (1 + 0.3275911 * ax)
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-ax * ax)
  return sign * y
}

export const histogramStats = (zs: number[]): HistogramStats => {
  const n = zs.length
  if (n === 0) {
    return { count: 0, mean: 0, stdev: 0, min: 0, max: 0, q1: 0, median: 0, q3: 0, skewness: 0, kurtosis: 0, cv: 0 }
  }
  const mean = meanOf(zs)
  const stdev = populationStd(zs, mean)
  const sorted = [...zs].sort((a, b) => a - b)

  let skewness = 0
  let kurtosis = 0
  if (stdev > 0 && n >= 3) {
    let s3 = 0
    for (const z of zs) s3 += ((z - mean) / stdev) ** 3
    skewness = s3 / n
  }
  if (stdev > 0 && n >= 4) {
    let s4 = 0
    for (const z of zs) s4 += ((z - mean) / stdev) ** 4
    kurtosis = s4 / n - 3
  }

  return {
    count: n,
    mean,
    stdev,
    min: sorted[0]!,
    max: sorted[n - 1]!,
    q1: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    q3: quantile(sorted, 0.75),
    skewness,
    kurtosis,
    cv: mean !== 0 ? (stdev / Math.abs(mean)) * 100 : 0
  }
}

export const resolveBinCount = (
  zs: number[],
  method: BinMethod,
  customCount: number
): number => {
  if (method === 'custom') return clampBins(customCount)
  const n = zs.length
  if (n < 1) return 5

  const sturges = clampBins(Math.ceil(1 + Math.log2(n)))
  const sorted = [...zs].sort((a, b) => a - b)
  const range = sorted[n - 1]! - sorted[0]!
  const iqr = quantile(sorted, 0.75) - quantile(sorted, 0.25)
  const fd = (iqr > 0 && range > 0)
    ? clampBins(Math.ceil(range / (2 * iqr * Math.pow(n, -1 / 3))))
    : sturges

  const mean = meanOf(zs)
  const std = populationStd(zs, mean)
  let outliers = 0
  if (std > 0) {
    for (const z of zs) if (Math.abs(z - mean) > 3 * std) outliers++
  }
  return outliers / n > 0.05 ? fd : sturges
}

export const computeHistogram = (
  zs: number[],
  binCount: number,
  mode: HistogramMode
): HistogramBins => {
  const n = zs.length
  const bins = Math.max(1, binCount)
  if (n === 0) return { centers: [0], values: [0], binWidth: 1, edges: [0, 1] }

  let min = Infinity
  let max = -Infinity
  for (const z of zs) {
    if (z < min) min = z
    if (z > max) max = z
  }
  if (max - min === 0) {
    return { centers: [min], values: [n], binWidth: 1, edges: [min - 0.5, min + 0.5] }
  }

  const binWidth = (max - min) / bins
  const counts = new Array(bins).fill(0)
  for (const z of zs) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((z - min) / binWidth)))
    counts[idx] += 1
  }
  const edges = Array.from({ length: bins + 1 }, (_, i) => min + binWidth * i)
  const centers = Array.from({ length: bins }, (_, i) => min + binWidth * (i + 0.5))

  let values: number[]
  if (mode === 'density') {
    values = counts.map(c => c / (n * binWidth))
  } else if (mode === 'cumulative') {
    let run = 0
    values = counts.map(c => (run += c))
  } else {
    values = counts
  }
  return { centers, values, binWidth, edges }
}

// Fitted normal evaluated at each bin center, scaled to the display mode:
// 'density' = pdf; 'frequency' = pdf · N · binWidth; 'cumulative' = cdf · N.
// Returns [] when stdev is 0 (no meaningful curve).
export const normalCurveOverCenters = (
  stats: HistogramStats,
  mode: HistogramMode,
  binWidth: number,
  centers: number[]
): number[] => {
  const { mean, stdev, count } = stats
  if (stdev <= 0 || count === 0) return []
  const pdf = (x: number) =>
    Math.exp(-((x - mean) ** 2) / (2 * stdev * stdev)) / (stdev * Math.sqrt(2 * Math.PI))
  const cdf = (x: number) => 0.5 * (1 + erf((x - mean) / (stdev * Math.SQRT2)))
  return centers.map((x) => {
    if (mode === 'density') return pdf(x)
    if (mode === 'cumulative') return cdf(x) * count
    return pdf(x) * count * binWidth
  })
}

// Index of the bin whose [edge_i, edge_{i+1}) contains `value`; clamped to a valid bin.
export const binIndexForValue = (edges: number[], value: number): number => {
  const bins = edges.length - 1
  if (bins <= 1) return 0
  for (let i = 0; i < bins; i++) {
    if (value < edges[i + 1]!) return Math.max(0, i)
  }
  return bins - 1
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/afmHistogram.test.ts`
Expected: PASS (13 tests).

- [ ] **Step 5: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors in `utils/afmHistogram.ts`.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/utils/afmHistogram.ts app/utils/afmHistogram.test.ts
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add pure histogram binning/stats helpers`

---

### Task 2: Wire controls into `HistogramChart.vue`

**Files:**
- Modify: `front-dev-home/app/components/afm/detail/HistogramChart.vue`

**Interfaces:**
- Consumes (auto-imported): `histogramStats`, `resolveBinCount`, `computeHistogram`, `normalCurveOverCenters`, `binIndexForValue`; types `BinMethod`/`HistogramMode`/`HistogramStats` via `import type`.

> No unit test — `.vue` wiring. Gate: `npm run typecheck` + `npm run lint`, plus in-app verification (Task 3).

- [ ] **Step 1: Replace the component with the controls-enabled version**

Replace the entire contents of `front-dev-home/app/components/afm/detail/HistogramChart.vue` with:

```vue
<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-bar-chart-3"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Z-value distribution
          </h2>
        </div>
        <p
          v-if="stats.count"
          class="sk-meta tabular-nums"
        >
          μ={{ stats.mean.toFixed(2) }} · σ={{ stats.stdev.toFixed(2) }}
          · Q1={{ stats.q1.toFixed(2) }} · Md={{ stats.median.toFixed(2) }} · Q3={{ stats.q3.toFixed(2) }}
          · skew={{ stats.skewness.toFixed(2) }} · kurt={{ stats.kurtosis.toFixed(2) }} · CV={{ stats.cv.toFixed(1) }}%
        </p>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-60 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading distribution…
    </div>
    <div
      v-else-if="profile.length === 0"
      class="flex h-60 items-center justify-center text-center sk-body"
    >
      No distribution data
    </div>
    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <USelect
          v-model="binMethod"
          :items="binMethodItems"
          size="xs"
          class="min-w-28"
          aria-label="Bin method"
        />
        <UInput
          v-if="binMethod === 'custom'"
          v-model.number="customBins"
          type="number"
          size="xs"
          class="w-20"
          :min="5"
          :max="200"
          aria-label="Bin count"
        />
        <USelect
          v-model="displayMode"
          :items="displayModeItems"
          size="xs"
          class="min-w-28"
          aria-label="Display mode"
        />
        <UCheckbox
          v-model="showNormal"
          label="Normal"
          size="xs"
        />
        <UCheckbox
          v-model="showPercentiles"
          label="Quartiles"
          size="xs"
        />
      </div>
      <div
        ref="chartEl"
        class="h-60 w-full"
      />
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { BinMethod, HistogramMode } from '~/utils/afmHistogram'

const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const binMethod = ref<BinMethod>('auto')
const customBins = ref<number>(30)
const displayMode = ref<HistogramMode>('frequency')
const showNormal = ref(true)
const showPercentiles = ref(true)

const binMethodItems: { label: string, value: BinMethod }[] = [
  { label: 'Auto bins', value: 'auto' },
  { label: 'Custom bins', value: 'custom' }
]
const displayModeItems: { label: string, value: HistogramMode }[] = [
  { label: 'Frequency', value: 'frequency' },
  { label: 'Density', value: 'density' },
  { label: 'Cumulative', value: 'cumulative' }
]

const zs = computed(() => props.profile.map(p => p.z))
const stats = computed(() => histogramStats(zs.value))
const binCount = computed(() => resolveBinCount(zs.value, binMethod.value, customBins.value))
const hist = computed(() => computeHistogram(zs.value, binCount.value, displayMode.value))

const centerLabels = computed(() => hist.value.centers.map(c => c.toFixed(2)))

const normalSeriesData = computed(() =>
  showNormal.value
    ? normalCurveOverCenters(stats.value, displayMode.value, hist.value.binWidth, hist.value.centers)
    : []
)

const percentileMarks = computed(() => {
  if (!showPercentiles.value || !stats.value.count) return []
  const edges = hist.value.edges
  return [
    { name: 'Q1', xAxis: binIndexForValue(edges, stats.value.q1) },
    { name: 'Md', xAxis: binIndexForValue(edges, stats.value.median) },
    { name: 'Q3', xAxis: binIndexForValue(edges, stats.value.q3) }
  ]
})

const yAxisName = computed(() =>
  displayMode.value === 'density' ? 'Density'
    : displayMode.value === 'cumulative' ? 'Cumulative' : 'Frequency'
)

const chartOption = computed<EChartsOption>(() => {
  const series: EChartsOption['series'] = [{
    type: 'bar',
    data: hist.value.values,
    itemStyle: { borderRadius: [3, 3, 0, 0] },
    markLine: percentileMarks.value.length
      ? {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed', color: '#94a3b8' },
          label: { fontSize: 9, formatter: (p: { name?: string }) => p.name ?? '' },
          data: percentileMarks.value
        }
      : undefined
  }]

  if (normalSeriesData.value.length) {
    series.push({
      type: 'line',
      data: normalSeriesData.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#ef4444', width: 2 },
      z: 3
    })
  }

  return {
    grid: { left: 46, right: 12, top: 16, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: centerLabels.value,
      axisLabel: { fontSize: 10, interval: Math.max(0, Math.ceil(centerLabels.value.length / 8) - 1) }
    },
    yAxis: {
      type: 'value',
      name: yAxisName.value,
      nameTextStyle: { fontSize: 9 },
      axisLabel: { fontSize: 10 }
    },
    series
  }
})

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors attributable to `HistogramChart.vue`. Pre-existing `RadiusChart.vue` errors are unrelated.

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors in `HistogramChart.vue`. If ESLint reports auto-fixable stylistic issues, run `npx eslint --fix app/components/afm/detail/HistogramChart.vue` and re-lint.

- [ ] **Step 4: Commit**

```bash
cd front-dev-home && git add app/components/afm/detail/HistogramChart.vue
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add bin/mode/overlay controls to Z-histogram`

---

### Task 3: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Frontend suite + gates**

Run: `cd front-dev-home && npm run test && npm run typecheck && npm run lint`
Expected: `afmHistogram.test.ts` passes with the rest; typecheck shows only pre-existing unrelated `RadiusChart.vue` errors; lint clean for the changed files. (`chatMarkdown.test.ts` / `relativeTime.test.ts` failures are the user's unrelated chat WIP, not this work.)

- [ ] **Step 2: In-app verification (verify skill)**

With Flask (`:5050`) and Nuxt (`:3000`) running, open an AFM detail page with a profiled point and confirm:
  - Controls: bin method (Auto/Custom + count when custom), display mode, Normal + Quartiles checkboxes.
  - Switching Auto↔Custom changes bin granularity; Density/Cumulative change the Y axis and shape; the red normal curve overlays the bars and the Q1/Md/Q3 dashed marklines appear at the quartiles.
  - The extended stats line (μ σ Q1 Md Q3 skew kurt CV) reads sensibly.
  - The hover PNG-download button still works.

- [ ] **Step 3: Markdown lint (only if docs changed)**

Run `npm run lint:md` from repo root only if any docs changed (none expected in Tasks 1-2).

---

## Self-Review

**Spec coverage:**

- Bin method Auto (Sturges/FD, FD when >5% 3σ outliers) / Custom(clamp 5–200) → Task 1 `resolveBinCount` + tests; Task 2 controls. ✓
- Display mode Frequency/Density/Cumulative → Task 1 `computeHistogram` (+ integrate-to-1 / monotonic tests); Task 2 select + Y-axis name. ✓
- Normal-curve overlay (toggle, scaled per mode, empty when stdev 0) → Task 1 `normalCurveOverCenters` + tests; Task 2 line series. ✓
- Percentile marklines (toggle, Q1/median/Q3) → Task 1 `binIndexForValue` + test; Task 2 `markLine`. ✓
- Extended numeric stats (μ σ min max Q1 Md Q3 skew kurt CV) → Task 1 `histogramStats` + tests; Task 2 header line. ✓
- Dropped prose/log-scale/Fine/CSV → not present. ✓
- Degenerate-data no-throw → Task 1 guards + empty/zero-span tests. ✓

**Placeholder scan:** No TBD/TODO; complete code in every step. ✓

**Type consistency:** `BinMethod`/`HistogramMode`/`HistogramStats`/`HistogramBins` defined in Task 1 and consumed by the same names in Task 2; `histogramStats`/`resolveBinCount`/`computeHistogram`/`normalCurveOverCenters`/`binIndexForValue` signatures match between util, tests, and component; `exportName` preserved so the PNG export keeps working. ✓
