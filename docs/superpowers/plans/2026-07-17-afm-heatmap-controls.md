# AFM Heatmap Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curated controls to the AFM wafer heatmap — outlier removal (None/IQR/Z-Score + threshold), color scheme (Spectral/Viridis/Grayscale), and a min/max/mean + "N removed" stats readout.

**Architecture:** Pure analysis logic (outlier bounds, stats, color ramps) goes in a new `utils/afmHeatmap.ts` unit-tested with `node --test`; `HeatmapChart.vue` gains `USelect`/`UInput` controls and wires the util into its existing `useEchart` chart option. No backend change.

**Tech Stack:** Nuxt 4 + NuxtUI v4.6.1 (`USelect`, `UInput`, `UBadge`), ECharts (`useEchart`), TypeScript, Node's built-in test runner.

## Global Constraints

- Frontend root `front-dev-home/`; run `npm` there. Tests: `node --test app/utils/afmHeatmap.test.ts`. Gates: `npm run typecheck`, `npm run lint`.
- `spectral` ramp MUST equal the current heatmap ramp exactly — `['#3b82f6', '#10b981', '#f59e0b', '#ef4444']` — so the default look does not change.
- Outlier defaults: IQR threshold 1.5, Z-Score threshold 3. Default method is `none` (show all).
- Degenerate data never blanks the chart: `none`, `< 4` points, non-finite/≤0 threshold, or zero spread (IQR 0 / std 0) → all points kept, `removed = 0`.
- Pure util has no DOM/Nuxt runtime imports (type-only import of `AfmProfilePoint`); the `.vue` file relies on Nuxt auto-import for the util's runtime exports and `import type` for its types.
- Work on `main`; commit per task; do NOT push. Tree has UNRELATED concurrent user WIP (`.remember/`, `docs/` deletions, a "chat" feature). Each task `git add`s ONLY its explicit files — never `git add -A`/`git add .`/`git stash`.
- Every commit message ends with:

  ```text
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NHWMRqfxSYaLcagApFG1tB
  ```

---

### Task 1: Pure heatmap logic (`utils/afmHeatmap.ts`)

**Files:**
- Create: `front-dev-home/app/utils/afmHeatmap.ts`
- Test: `front-dev-home/app/utils/afmHeatmap.test.ts`

**Interfaces:**
- Consumes: `AfmProfilePoint` (type-only) from `~/composables/useAfmDetailApi`.
- Produces: `OutlierMethod`, `HeatmapColorScheme`, `OUTLIER_DEFAULT_THRESHOLD`, `HEATMAP_COLOR_RAMPS`, `HeatmapFilterResult`, `HeatmapStats`, `filterProfileByOutlier(points, method, threshold)`, `heatmapStats(points)`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/afmHeatmap.test.ts`:

```ts
// Pure-logic tests for afmHeatmap. Run: node --test app/utils/afmHeatmap.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  filterProfileByOutlier,
  heatmapStats,
  OUTLIER_DEFAULT_THRESHOLD,
  HEATMAP_COLOR_RAMPS
} from './afmHeatmap.ts'

const pts = (zs: number[]) => zs.map((z, i) => ({ x: i, y: i, z }))

test('none keeps all points', () => {
  const r = filterProfileByOutlier(pts([1, 2, 3, 100]), 'none', 1.5)
  assert.equal(r.removed, 0)
  assert.equal(r.kept.length, 4)
})

test('iqr removes a planted high outlier', () => {
  const r = filterProfileByOutlier(pts([10, 11, 12, 13, 12, 11, 200]), 'iqr', 1.5)
  assert.equal(r.removed, 1)
  assert.ok(!r.kept.some(p => p.z === 200))
})

test('zscore removes a planted outlier', () => {
  const r = filterProfileByOutlier(pts([5, 5, 5, 5, 5, 5, 60]), 'zscore', 2)
  assert.ok(r.removed >= 1)
  assert.ok(!r.kept.some(p => p.z === 60))
})

test('fewer than 4 points keeps all', () => {
  const r = filterProfileByOutlier(pts([1, 999, 2]), 'iqr', 1.5)
  assert.equal(r.removed, 0)
})

test('all-equal z (zero spread) keeps all', () => {
  assert.equal(filterProfileByOutlier(pts([7, 7, 7, 7, 7]), 'iqr', 1.5).removed, 0)
  assert.equal(filterProfileByOutlier(pts([7, 7, 7, 7, 7]), 'zscore', 3).removed, 0)
})

test('non-finite or non-positive threshold keeps all', () => {
  assert.equal(filterProfileByOutlier(pts([1, 2, 3, 100]), 'iqr', NaN).removed, 0)
  assert.equal(filterProfileByOutlier(pts([1, 2, 3, 100]), 'iqr', 0).removed, 0)
})

test('heatmapStats computes count/min/max/mean', () => {
  const s = heatmapStats(pts([2, 4, 6]))
  assert.deepEqual(s, { count: 3, min: 2, max: 6, mean: 4 })
})

test('heatmapStats on empty → zeros', () => {
  assert.deepEqual(heatmapStats([]), { count: 0, min: 0, max: 0, mean: 0 })
})

test('spectral ramp is unchanged from the current heatmap', () => {
  assert.deepEqual(HEATMAP_COLOR_RAMPS.spectral, ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'])
})

test('every color ramp is a non-empty string array; defaults present', () => {
  for (const ramp of Object.values(HEATMAP_COLOR_RAMPS)) {
    assert.ok(Array.isArray(ramp) && ramp.length > 0)
  }
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.iqr, 1.5)
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.zscore, 3)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/afmHeatmap.test.ts`
Expected: FAIL — `Cannot find module './afmHeatmap.ts'`.

- [ ] **Step 3: Write `afmHeatmap.ts`**

Create `front-dev-home/app/utils/afmHeatmap.ts`:

```ts
// Pure heatmap analysis helpers for the AFM wafer heat map. No DOM/Nuxt imports
// so they run under `node --test`; HeatmapChart.vue wires them into useEchart.
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

export type OutlierMethod = 'none' | 'iqr' | 'zscore'
export type HeatmapColorScheme = 'spectral' | 'viridis' | 'grayscale'

export const OUTLIER_DEFAULT_THRESHOLD: Record<OutlierMethod, number> = {
  none: 0,
  iqr: 1.5,
  zscore: 3
}

// 'spectral' MUST match the pre-existing heatmap ramp so the default look is unchanged.
export const HEATMAP_COLOR_RAMPS: Record<HeatmapColorScheme, string[]> = {
  spectral: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
  viridis: ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'],
  grayscale: ['#111827', '#6b7280', '#e5e7eb']
}

export interface HeatmapFilterResult {
  kept: AfmProfilePoint[]
  removed: number
}

export interface HeatmapStats {
  count: number
  min: number
  max: number
  mean: number
}

const mean = (nums: number[]): number =>
  nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0

const stdev = (nums: number[], mu: number): number => {
  if (nums.length < 2) return 0
  const variance = nums.reduce((a, b) => a + (b - mu) ** 2, 0) / nums.length
  return Math.sqrt(variance)
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

export const filterProfileByOutlier = (
  points: AfmProfilePoint[],
  method: OutlierMethod,
  threshold: number
): HeatmapFilterResult => {
  if (method === 'none' || points.length < 4 || !Number.isFinite(threshold) || threshold <= 0) {
    return { kept: points, removed: 0 }
  }

  const zs = points.map(p => p.z)
  let lower: number
  let upper: number

  if (method === 'zscore') {
    const mu = mean(zs)
    const sd = stdev(zs, mu)
    if (sd === 0) return { kept: points, removed: 0 }
    lower = mu - threshold * sd
    upper = mu + threshold * sd
  } else {
    const sorted = [...zs].sort((a, b) => a - b)
    const q1 = quantile(sorted, 0.25)
    const q3 = quantile(sorted, 0.75)
    const iqr = q3 - q1
    if (iqr === 0) return { kept: points, removed: 0 }
    lower = q1 - threshold * iqr
    upper = q3 + threshold * iqr
  }

  const kept = points.filter(p => p.z >= lower && p.z <= upper)
  return { kept, removed: points.length - kept.length }
}

export const heatmapStats = (points: AfmProfilePoint[]): HeatmapStats => {
  if (points.length === 0) return { count: 0, min: 0, max: 0, mean: 0 }
  let min = Infinity
  let max = -Infinity
  let sum = 0
  for (const p of points) {
    if (p.z < min) min = p.z
    if (p.z > max) max = p.z
    sum += p.z
  }
  return { count: points.length, min, max, mean: sum / points.length }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/afmHeatmap.test.ts`
Expected: PASS (10 tests).

- [ ] **Step 5: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors in `utils/afmHeatmap.ts`.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/utils/afmHeatmap.ts app/utils/afmHeatmap.test.ts
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add pure heatmap outlier/stats helpers`

---

### Task 2: Wire controls into `HeatmapChart.vue`

**Files:**
- Modify: `front-dev-home/app/components/afm/detail/HeatmapChart.vue`

**Interfaces:**
- Consumes: `filterProfileByOutlier`, `heatmapStats`, `OUTLIER_DEFAULT_THRESHOLD`, `HEATMAP_COLOR_RAMPS` (auto-imported), and types `OutlierMethod`/`HeatmapColorScheme` (via `import type`).

> No unit test — `.vue` wiring. Gate: `npm run typecheck` + `npm run lint`, plus in-app verification (Task 3).

- [ ] **Step 1: Replace the component with the controls-enabled version**

Replace the entire contents of `front-dev-home/app/components/afm/detail/HeatmapChart.vue` with:

```vue
<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-grid-3x3"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Wafer heat map
          </h2>
        </div>
        <div
          v-if="stats.count"
          class="flex items-center gap-2 sk-meta tabular-nums"
        >
          <span>{{ stats.count.toLocaleString() }} pts</span>
          <span>min {{ stats.min.toFixed(2) }}</span>
          <span>max {{ stats.max.toFixed(2) }}</span>
          <span>μ {{ stats.mean.toFixed(2) }}</span>
          <UBadge
            v-if="filtered.removed > 0"
            :label="`${filtered.removed} removed`"
            color="warning"
            size="xs"
            variant="subtle"
          />
        </div>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-72 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading heat map…
    </div>
    <div
      v-else-if="profile.length === 0"
      class="flex h-72 items-center justify-center text-center sk-body"
    >
      Heat map data unavailable
    </div>
    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <USelect
          v-model="outlierMethod"
          :items="outlierMethodItems"
          size="xs"
          class="min-w-36"
          aria-label="Outlier method"
        />
        <UInput
          v-if="outlierMethod !== 'none'"
          v-model.number="threshold"
          type="number"
          size="xs"
          class="w-24"
          :step="0.1"
          aria-label="Outlier threshold"
        />
        <USelect
          v-model="colorScheme"
          :items="colorSchemeItems"
          size="xs"
          class="min-w-28"
          aria-label="Color scheme"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { OutlierMethod, HeatmapColorScheme } from '~/utils/afmHeatmap'

const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const outlierMethod = ref<OutlierMethod>('none')
const threshold = ref<number>(OUTLIER_DEFAULT_THRESHOLD.iqr)
const colorScheme = ref<HeatmapColorScheme>('spectral')

const outlierMethodItems: { label: string, value: OutlierMethod }[] = [
  { label: 'No outlier filter', value: 'none' },
  { label: 'IQR', value: 'iqr' },
  { label: 'Z-Score', value: 'zscore' }
]
const colorSchemeItems: { label: string, value: HeatmapColorScheme }[] = [
  { label: 'Spectral', value: 'spectral' },
  { label: 'Viridis', value: 'viridis' },
  { label: 'Grayscale', value: 'grayscale' }
]

watch(outlierMethod, (method) => {
  if (method !== 'none') threshold.value = OUTLIER_DEFAULT_THRESHOLD[method]
})

const filtered = computed(() =>
  filterProfileByOutlier(props.profile, outlierMethod.value, threshold.value)
)
const stats = computed(() => heatmapStats(filtered.value.kept))

const formatTooltip = (params: unknown) => {
  const value = (params as { value?: unknown }).value
  if (!Array.isArray(value)) return ''
  const [x, y, z] = value
  if (typeof x !== 'number' || typeof y !== 'number' || typeof z !== 'number') return ''
  return `x: ${x.toFixed(1)}<br/>y: ${y.toFixed(1)}<br/>z: ${z.toFixed(2)}`
}

const zRange = computed(() =>
  stats.value.count ? [stats.value.min, stats.value.max] : [0, 1]
)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 50, right: 60, top: 16, bottom: 36 },
  tooltip: {
    formatter: formatTooltip
  },
  xAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  visualMap: {
    min: zRange.value[0],
    max: zRange.value[1],
    calculable: true,
    orient: 'vertical',
    right: 4,
    top: 'center',
    inRange: { color: HEATMAP_COLOR_RAMPS[colorScheme.value] },
    textStyle: { fontSize: 10 }
  },
  series: [{
    type: 'scatter',
    symbolSize: 8,
    data: filtered.value.kept.map(p => [p.x, p.y, p.z])
  }]
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors attributable to `HeatmapChart.vue`. (If `USelect` v-model complains about the union type, confirm `outlierMethodItems`/`colorSchemeItems` are typed `{ label: string, value: OutlierMethod | HeatmapColorScheme }[]` as written.) Pre-existing `RadiusChart.vue` errors are unrelated.

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors in `HeatmapChart.vue`. If ESLint reports auto-fixable stylistic issues, run `npx eslint --fix app/components/afm/detail/HeatmapChart.vue` and re-lint.

- [ ] **Step 4: Commit**

```bash
cd front-dev-home && git add app/components/afm/detail/HeatmapChart.vue
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add outlier/color-scheme controls to wafer heatmap`

---

### Task 3: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Frontend suite + gates**

Run: `cd front-dev-home && npm run test && npm run typecheck && npm run lint`
Expected: `afmHeatmap.test.ts` passes with the rest; typecheck shows only the pre-existing unrelated `RadiusChart.vue` errors; lint clean for the changed files. (Note: `chatMarkdown.test.ts` / `relativeTime.test.ts` failures are the user's unrelated chat WIP, not this work.)

- [ ] **Step 2: In-app verification (verify skill)**

With Flask (`:5050`) and Nuxt (`:3000`) running, open an AFM detail page with a selected point that has a profile (e.g. tool `map608`, point `1_UL`) and confirm:
  - The heatmap shows three controls (outlier method, threshold when not "none", color scheme).
  - Switching to IQR/Z-Score refilters the chart and the header shows an "N removed" badge; min/max/mean update.
  - Switching color scheme recolors without refiltering.
  - The default view (method "none", Spectral) looks identical to before this change.
  - The hover PNG-download button still works.

- [ ] **Step 3: Markdown lint (only if docs changed)**

Run `npm run lint:md` from repo root only if any docs changed (none expected in Tasks 1-2).

---

## Self-Review

**Spec coverage:**

- Outlier removal None/IQR/Z-Score + threshold (defaults 1.5/3) → Task 1 `filterProfileByOutlier` + Task 2 controls. ✓
- Color scheme Spectral/Viridis/Grayscale, spectral == current ramp → Task 1 `HEATMAP_COLOR_RAMPS` + regression test + Task 2 wiring. ✓
- Stats readout min/max/mean + "N removed" → Task 1 `heatmapStats` + Task 2 header. ✓
- Degenerate-data no-blank guarantee → Task 1 guards + tests (<4 pts, zero spread, bad threshold). ✓
- Dropped sampling / CSV / click-select → not present (correct). ✓
- Pure logic tested; component gated by typecheck/lint/in-app → Tasks 1-3. ✓

**Placeholder scan:** No TBD/TODO; complete code in every step. ✓

**Type consistency:** `OutlierMethod`/`HeatmapColorScheme`/`HeatmapFilterResult`/`HeatmapStats` defined in Task 1 and consumed by the same names in Task 2; `filterProfileByOutlier`/`heatmapStats` signatures match between util, tests, and component; `exportName` prop preserved so the existing PNG export (Sub-project A) keeps working. ✓
