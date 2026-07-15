# 스큐보아 B1 — 측정 개요 (Measurement Overview) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the single-measurement analysis view as the "측정 개요" (answer-first Option A): an active-parameter verdict strip, a per-parameter navigator, honesty-gated failure/outlier evidence, reworked measurement-condition/alignment panel, and cross-panel linked selection.

**Architecture:** All B1 analytics collapse into one pure, unit-tested function `overviewSites()` (coverage + outlier count + status + table rows) that every panel renders — so coverage, outlier badge, wafer `◎`, and the navigator column can never disagree. A shared `focusedSequence` state in `useSkewvoirAnalysis` links the wafer map, radius plot, measurement-points table, and SEM image. Layout is a 12-column grid in `views/Dashboard.vue`.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), NuxtUI, ECharts (via `useEchart`), Node built-in test runner (`node --test`) for pure utils. TypeScript throughout.

## Global Constraints

- **Failures never enter statistics.** A row is measured iff `isMeasuredRow(row)` (`cd_value !== null && mp_number >= 0`). Never coerce `cd_value: null` to 0. (spec §3.1, §7)
- **One definition of "outlier."** Site anomaly is `siteVerdicts()` (leave-one-out) only — no second IQR/threshold path. `status` ('evaluated' | 'insufficient') stays separate from `severity` ('normal' | 'watch' | 'abnormal'). (spec §9.5)
- **이상 사이트 count = `abnormal` + `watch`** (evaluated only). Failures are a separate axis, excluded from this count. (spec §9.1)
- **No fabricated "평가 불가" → 정상.** When `status === 'insufficient'` (or no denominator), a panel shows the reason, never a misleading number. (spec §11.2)
- **Vendor score / `spm_dict` / `MsrFileResponse.health` are never inputs to judgment or sorting.** (spec §3.2, §5.2)
- **Keep the `dashboard` view slug.** Relabel display text only; do not rename `kind: 'dashboard'` (preserves `?view=dashboard` links and tests). (spec §9.4)
- **Korean UI copy**, formal endings where sentences appear.
- **Tests:** pure utils use `node --test` (run: `npm --prefix front-dev-home test`; single file: `cd front-dev-home && node --test app/utils/<file>.test.ts`). Components have no unit-test infra — verify live via the project `verify` skill, gated by `npm --prefix front-dev-home run typecheck` and `npm --prefix front-dev-home run lint`.

---

## File Structure

**Create:**
- `front-dev-home/app/utils/overview.ts` — pure B1 analytics: `overviewSites(rows, parameter, config)` → coverage + outlierCount + status + tableRows.
- `front-dev-home/app/utils/overview.test.ts` — `node --test` unit tests for the above.
- `front-dev-home/app/components/ebeam/skewvoir/overview/VerdictStrip.vue` — 4-card verdict strip (follows active param).
- `front-dev-home/app/components/ebeam/skewvoir/overview/SiteVerdicts.vue` — 이상·실패 사이트 table; click a row to focus its sequence.

**Modify:**
- `front-dev-home/app/composables/useSkewvoirAnalysis.ts` — add `focusedSequence` + `setFocusedSequence`, `activeOverview`, `overviewFor`.
- `front-dev-home/app/composables/useSkewvoirWorkspace.ts` — delete `health` state; relabel the `dashboard` view mode.
- `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue` — delete the HEALTH section.
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/DataSummary.vue` — add COVERAGE + OUT columns (parameter navigator).
- `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue` — plot failures (`✕`) and outlier rings (`◎`); click-to-focus + focus highlight.
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue` — pass focus/click through to the chart.
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/Acquisition.vue` — read `exe_detail_info` + `alignment` + representative `meas_condition_*`.
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue` — click row → focus; highlight focused row.
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/SemImage.vue` — show the focused sequence's image.
- `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue` — click point → focus; highlight focused point.
- `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue` — Option A layout (verdict strip → navigator → inspection zone).

---

## Task 1: `overviewSites` pure analytics util

**Files:**
- Create: `front-dev-home/app/utils/overview.ts`
- Test: `front-dev-home/app/utils/overview.test.ts`

**Interfaces:**
- Consumes: `siteVerdicts` (`~/utils/anomaly/site`), `isMeasuredRow` (`~/utils/msrRows`), `MethodConfig`/`EvalStatus`/`DEFAULT_METHOD_CONFIG` (`~/utils/anomaly/types`), `MsrFileRow` (`~/composables/useMsrFileApi`).
- Produces: `overviewSites(rows: MsrFileRow[], parameter: string, config?: MethodConfig): OverviewSites` where `OverviewSites = { coverage: { total, measured, failed }, outlierCount: number, status: EvalStatus, tableRows: OverviewSiteRow[] }` and `OverviewSiteRow = { sequence: number, chip: string, cd: number | null, delta: number | null, kind: 'abnormal' | 'watch' | 'failed' }`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/overview.test.ts`:

```ts
// front-dev-home/app/utils/overview.test.ts
// Pure-logic tests — run: cd front-dev-home && node --test app/utils/overview.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { overviewSites } from './overview.ts'
import { DEFAULT_METHOD_CONFIG } from './anomaly/types.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// 5 measured at 100, one at 160 (+~52% off LOO mean → abnormal), one failure.
const sample = (): MsrFileRow[] => [
  row({ sequence: 1, cd_value: 100 }),
  row({ sequence: 2, cd_value: 100 }),
  row({ sequence: 3, cd_value: 100 }),
  row({ sequence: 4, cd_value: 100 }),
  row({ sequence: 5, cd_value: 160, chip_number: '9, 9' }),
  row({ sequence: 6, cd_value: null, mp_number: -1, chip_number: '7, 2' })
]

test('coverage counts measured vs total, failures excluded from measured', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.deepEqual(ov.coverage, { total: 6, measured: 5, failed: 1 })
})

test('outlierCount is abnormal+watch only, never failures or normals', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.outlierCount, 1) // the 160 site; the null failure is NOT counted
})

test('tableRows include flagged + failed, exclude normal sites', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  const kinds = ov.tableRows.map(r => r.kind)
  assert.ok(kinds.includes('abnormal'))
  assert.ok(kinds.includes('failed'))
  assert.equal(kinds.filter(k => k === 'abnormal' || k === 'watch').length, 1)
  assert.equal(ov.tableRows.length, 2) // 1 flagged + 1 failed
})

test('a failed row carries null cd/delta and kind failed', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  const failed = ov.tableRows.find(r => r.kind === 'failed')!
  assert.equal(failed.sequence, 6)
  assert.equal(failed.cd, null)
  assert.equal(failed.delta, null)
})

test('flagged sorts before failed, flagged by |delta| desc', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.tableRows[0]!.kind, 'abnormal')
  assert.equal(ov.tableRows.at(-1)!.kind, 'failed')
})

test('too few measured sites → status insufficient, outlierCount 0', () => {
  const rows = [row({ sequence: 1, cd_value: 100 }), row({ sequence: 2, cd_value: 100 })]
  const ov = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.status, 'insufficient')
  assert.equal(ov.outlierCount, 0)
})

test('other parameters are ignored', () => {
  const rows = [
    ...sample(),
    row({ sequence: 7, parameter: 'CD_BOTTOM', cd_value: 5 })
  ]
  const ov = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.coverage.total, 6)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/overview.test.ts`
Expected: FAIL — `Cannot find module './overview.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/overview.ts`:

```ts
// front-dev-home/app/utils/overview.ts
// Pure B1 (측정 개요) analytics for ONE parameter: coverage, site outlier count,
// evaluation status, and the flagged/failed rows for the 이상·실패 사이트 table.
//
// This is the single source every overview panel renders, so the verdict strip,
// the navigator's OUT column, the wafer ◎ rings, and the site table can never
// disagree. "Outlier" here is exactly siteVerdicts (leave-one-out) — no second
// definition — and failures (cd_value: null) are a separate axis that never
// enters the outlier count or the statistics.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { EvalStatus, MethodConfig } from './anomaly/types.ts'
import { DEFAULT_METHOD_CONFIG } from './anomaly/types.ts'
import { siteVerdicts } from './anomaly/site.ts'
import { isMeasuredRow } from './msrRows.ts'

export interface ParamCoverage {
  total: number    // rows attempted for this parameter
  measured: number // rows with a real cd_value
  failed: number   // total - measured (cd_value: null)
}

export type SiteKind = 'abnormal' | 'watch' | 'failed'

export interface OverviewSiteRow {
  sequence: number
  chip: string          // chip_number, e.g. '-4, 6'
  cd: number | null     // null for a failed site
  delta: number | null  // signed % vs sibling sites (range method); null for failed
  kind: SiteKind
}

export interface OverviewSites {
  coverage: ParamCoverage
  outlierCount: number // sites with severity abnormal|watch (evaluated only)
  status: EvalStatus   // 'insufficient' when too few measured sites to judge
  tableRows: OverviewSiteRow[] // flagged + failed, sorted for the table
}

const KIND_RANK: Record<SiteKind, number> = { abnormal: 0, watch: 1, failed: 2 }

export const overviewSites = (
  rows: MsrFileRow[],
  parameter: string,
  config: MethodConfig = DEFAULT_METHOD_CONFIG
): OverviewSites => {
  const forParam = rows.filter(r => r.parameter === parameter)
  const measured = forParam.filter(isMeasuredRow)
  const coverage: ParamCoverage = {
    total: forParam.length,
    measured: measured.length,
    failed: forParam.length - measured.length
  }

  const verdicts = siteVerdicts(rows, parameter, config)
  // siteVerdicts assigns one shared status across the pool (peer-based), so the
  // first verdict's status represents the whole parameter. Empty → insufficient.
  const status: EvalStatus = verdicts[0]?.verdict.status ?? 'insufficient'

  const flagged: OverviewSiteRow[] = verdicts
    .filter(v => v.verdict.status === 'evaluated'
      && (v.verdict.severity === 'abnormal' || v.verdict.severity === 'watch'))
    .map(v => ({
      sequence: v.row.sequence,
      chip: v.row.chip_number,
      cd: v.row.cd_value,
      delta: v.verdict.score,
      kind: v.verdict.severity as 'abnormal' | 'watch'
    }))

  const failed: OverviewSiteRow[] = forParam
    .filter(r => !isMeasuredRow(r))
    .map(r => ({ sequence: r.sequence, chip: r.chip_number, cd: null, delta: null, kind: 'failed' as const }))

  const tableRows = [...flagged, ...failed].sort((a, b) => {
    if (KIND_RANK[a.kind] !== KIND_RANK[b.kind]) return KIND_RANK[a.kind] - KIND_RANK[b.kind]
    if (a.kind === 'failed') return a.sequence - b.sequence
    return Math.abs(b.delta!) - Math.abs(a.delta!) // larger deviation first
  })

  return { coverage, outlierCount: flagged.length, status, tableRows }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/overview.test.ts`
Expected: PASS — 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/overview.ts front-dev-home/app/utils/overview.test.ts
git commit -m "feat(skewvoir): add overviewSites — coverage, outlier count, site table (B1)"
```

---

## Task 2: Delete HEALTH block + relabel nav to 측정 개요

**Files:**
- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue`

**Interfaces:**
- Produces: `SKEWVOIR_VIEW_MODES[0]` now `{ kind: 'dashboard', index: 1, label: '측정 개요', sub: 'Measurement Overview', icon: 'i-lucide-clipboard-check' }`. The `SkewvoirWorkspace` object no longer exposes `health`.

- [ ] **Step 1: Relabel the dashboard view mode**

In `useSkewvoirWorkspace.ts`, replace the first entry of `SKEWVOIR_VIEW_MODES`:

```ts
  { kind: 'dashboard', index: 1, label: '측정 개요', sub: 'Measurement Overview', icon: 'i-lucide-clipboard-check' },
```

- [ ] **Step 2: Delete the health state**

In `useSkewvoirWorkspace.ts`, delete the `SkewvoirHealth` interface, the `health` `useState` line (the `Health stays mock-seeded…` comment + `const health = useState<SkewvoirHealth>(...)`), and remove `health` from the returned object. Also delete the now-unused `SkewvoirHealth` export.

- [ ] **Step 3: Delete the HEALTH section in LeftRail**

In `LeftRail.vue`, delete the entire `<!-- Health -->` `<section class="mt-auto …">…</section>` block (the `HEALTH · LAST 31H` markup). Nothing else in the file references `ws.health`.

- [ ] **Step 4: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS, no references to `health` / `SkewvoirHealth` remain.

- [ ] **Step 5: Verify live**

Use the `verify` skill. Open a cd-sem skewvoir analysis link. Confirm: left rail shows "측정 개요 / Measurement Overview" as item 1, and the "HEALTH · LAST 31H" block is gone.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/useSkewvoirWorkspace.ts front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue
git commit -m "refactor(skewvoir): drop hardcoded HEALTH block, relabel dashboard → 측정 개요 (B1 §3.4/§9.4)"
```

---

## Task 3: Extend `useSkewvoirAnalysis` — focusedSequence + overview derivations

**Files:**
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`

**Interfaces:**
- Consumes: `overviewSites` / `OverviewSites` (`~/utils/overview`).
- Produces (added to the returned object): `focusedSequence: Ref<number | null>`, `setFocusedSequence: (seq: number | null) => void`, `activeOverview: ComputedRef<OverviewSites>`, `overviewFor: (parameter: string) => OverviewSites`.

- [ ] **Step 1: Import the util**

At the top of `useSkewvoirAnalysis.ts`, add:

```ts
import { overviewSites, type OverviewSites } from '~/utils/overview'
```

- [ ] **Step 2: Add focus state + overview derivations**

After `activeSummary` / `activeUnit` / `siteRows` are defined (they already exist), insert:

```ts
  // Focused measurement point (sequence) — shared inspection state for linked
  // selection across the overview panels. useState so it survives remounts;
  // resets whenever the focus MSR or active parameter changes (a sequence only
  // identifies a point within one measurement + parameter).
  const focusedSequence = useState<number | null>(`skewvoir-focused-seq-${ws.toolType}`, () => null)
  const setFocusedSequence = (seq: number | null) => { focusedSequence.value = seq }
  watch([() => ws.selection.value?.msr, activeParam], () => { focusedSequence.value = null })

  // The B1 overview roll-up (coverage, outlier count, status, table rows) for the
  // ACTIVE parameter. overviewFor() computes the same for any parameter (navigator).
  const activeOverview = computed<OverviewSites>(() =>
    overviewSites(siteRows.value, activeParam.value, anomalyCfg.value)
  )
  const overviewFor = (parameter: string): OverviewSites =>
    overviewSites(siteRows.value, parameter, anomalyCfg.value)
```

- [ ] **Step 3: Export them**

Add `focusedSequence`, `setFocusedSequence`, `activeOverview`, `overviewFor` to the object returned at the end of `useSkewvoirAnalysis`.

- [ ] **Step 4: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useSkewvoirAnalysis.ts
git commit -m "feat(skewvoir): add focusedSequence + overview derivations to analysis composable (B1 §10.1)"
```

---

## Task 4: `DataSummary.vue` → parameter navigator (COVERAGE + OUT)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/DataSummary.vue`

**Interfaces:**
- Consumes: `analysis.paramSummaries`, `analysis.overviewFor(param)`, `analysis.activeParam`, `analysis.setParam`.

- [ ] **Step 1: Rewrite DataSummary with coverage + outlier columns**

Replace the entire file with:

```vue
<template>
  <EbeamSkewvoirPanelFrame
    title="파라미터"
    :meta="meta"
    icon="i-lucide-table-2"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-40 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
      불러오는 중…
    </div>
    <div v-else-if="rows.length" class="overflow-auto">
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">PARAMETER</th>
            <th class="px-2 py-1.5 font-medium">COVERAGE</th>
            <th class="px-2 py-1.5 text-right font-medium">MEAN</th>
            <th class="px-2 py-1.5 text-right font-medium">3Σ</th>
            <th class="px-2 py-1.5 text-right font-medium">OUT</th>
            <th class="px-2 py-1.5 font-medium">UNIT</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows"
            :key="r.parameter"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="r.parameter === analysis.activeParam.value ? 'bg-(--sk-brand)/8 font-medium' : 'hover:bg-(--sk-chip-bg)'"
            :aria-selected="r.parameter === analysis.activeParam.value"
            @click="analysis.setParam(r.parameter)"
          >
            <td class="px-2 py-1.5 font-mono text-zinc-800 dark:text-zinc-100">{{ r.parameter }}</td>
            <td class="px-2 py-1.5 font-mono tabular-nums" :class="r.failed > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink-muted)'">
              {{ r.measured }}/{{ r.total }}<span v-if="r.failed > 0" class="text-[10px]"> · {{ r.failed }} 실패</span>
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300">{{ r.mean.toFixed(3) }}</td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300">{{ (r.std * 3).toFixed(3) }}</td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="r.outlier > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink-subtle)'">
              {{ r.evaluated ? r.outlier : '—' }}
            </td>
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">{{ r.unit }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="flex h-40 items-center justify-center text-[12px] text-(--sk-ink-subtle)">
      파라미터 요약이 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// One row per parameter: backend summary (mean/std/unit) joined with the honest
// per-parameter coverage + outlier count from overviewFor(). The OUT column shows
// '—' when the parameter can't be judged (status insufficient) — never a fake 0.
const rows = computed(() =>
  props.analysis.paramSummaries.value.map((s) => {
    const ov = props.analysis.overviewFor(s.parameter)
    return {
      parameter: s.parameter,
      mean: s.mean,
      std: s.std,
      unit: s.unit,
      total: ov.coverage.total,
      measured: ov.coverage.measured,
      failed: ov.coverage.failed,
      outlier: ov.outlierCount,
      evaluated: ov.status === 'evaluated'
    }
  })
)

const meta = computed(() => `${rows.value.length} parameters`)
</script>
```

- [ ] **Step 2: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 3: Verify live**

Use the `verify` skill on a cd-sem analysis link. Confirm the table lists every parameter with COVERAGE (e.g. `43/45 · 2 실패`), 3Σ, and OUT; clicking a row switches the active parameter (wafer map / other panels re-render). A parameter with too few sites shows `—` under OUT.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/DataSummary.vue
git commit -m "feat(skewvoir): DataSummary → parameter navigator with coverage + outlier columns (B1 §9.2)"
```

---

## Task 5: `WaferMap.vue` — failure ✕, outlier ◎, click-to-focus + highlight

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue` (presentational chart)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue` (panel wrapper)

**Interfaces:**
- The presentational `WaferMap` gains props `focusedSequence: number | null` and emits `focus: [sequence: number]`. The wrapper wires these to `analysis.focusedSequence` / `analysis.setFocusedSequence`.

- [ ] **Step 1: Rewrite the presentational WaferMap**

Replace `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue` with:

```vue
<template>
  <div ref="chartEl" class="h-72 w-full" />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow, measuredRows } from '~/utils/msrRows'
import { siteVerdicts } from '~/utils/anomaly/site'
import { SK_CHART } from '~/utils/chartPalette'

const props = defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  focusedSequence: number | null
}>()
const emit = defineEmits<{ focus: [sequence: number] }>()

const forParam = computed(() => props.rows.filter(r => r.parameter === props.parameter))

// Measured points: one marker per chip position, colored by the mean cd_value at
// that position. `name` carries a sequence at that chip so clicks can focus.
const measuredPoints = computed(() => {
  const acc = new Map<string, { x: number, y: number, sum: number, n: number, seq: number }>()
  for (const r of measuredRows(forParam.value)) {
    const xy = parseChipXY(r.chip_number)
    if (!xy) continue
    const key = `${xy[0]},${xy[1]}`
    const e = acc.get(key) ?? { x: xy[0], y: xy[1], sum: 0, n: 0, seq: r.sequence }
    e.sum += r.cd_value
    e.n += 1
    acc.set(key, e)
  }
  return [...acc.values()].map(e => ({
    name: String(e.seq),
    value: [e.x, e.y, Number((e.sum / e.n).toFixed(3))]
  }))
})

// Failures (cd_value: null) as ✕ marks — a spatial cluster of ✕ is itself a finding.
const failurePoints = computed(() =>
  forParam.value.filter(r => !isMeasuredRow(r)).map((r) => {
    const xy = parseChipXY(r.chip_number)
    return xy ? { name: String(r.sequence), value: [xy[0], xy[1]] } : null
  }).filter((p): p is { name: string, value: number[] } => p !== null)
)

// Outlier sites (abnormal|watch) as ◎ rings — same siteVerdicts as everywhere.
const outlierPoints = computed(() => {
  const flagged = new Set(
    siteVerdicts(props.rows, props.parameter)
      .filter(v => v.verdict.status === 'evaluated' && v.verdict.severity !== 'normal')
      .map(v => v.row.sequence)
  )
  return measuredPoints.value.filter(p => flagged.has(Number(p.name)))
    .map(p => ({ name: p.name, value: [p.value[0], p.value[1]] }))
})

const focusPoint = computed(() => {
  if (props.focusedSequence == null) return []
  const hit = [...measuredPoints.value, ...failurePoints.value].find(p => Number(p.name) === props.focusedSequence)
  return hit ? [{ name: hit.name, value: [hit.value[0], hit.value[1]] }] : []
})

const valueRange = computed(() => {
  const values = measuredPoints.value.map(p => p.value[2] as number)
  if (values.length === 0) return { min: 0, max: 1 }
  return { min: Math.min(...values), max: Math.max(...values) }
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      const seq = (params as { name?: string }).name
      const val = v[2] != null ? `${props.parameter}: <b>${v[2]}</b> ${props.unit}` : '측정 실패'
      return `seq ${seq} · chip (${v[0]}, ${v[1]})<br/>${val}`
    }
  },
  grid: { left: 36, right: 16, top: 16, bottom: 28, containLabel: true },
  xAxis: { type: 'value', min: -11, max: 11, splitLine: { show: true }, axisLabel: { fontSize: 10 }, name: 'chip x', nameTextStyle: { fontSize: 10 } },
  yAxis: { type: 'value', min: -11, max: 11, splitLine: { show: true }, axisLabel: { fontSize: 10 }, name: 'chip y', nameTextStyle: { fontSize: 10 } },
  visualMap: {
    min: valueRange.value.min, max: valueRange.value.max, calculable: true, orient: 'vertical',
    right: 0, top: 'center', itemHeight: 120, textStyle: { fontSize: 10 },
    dimension: 2, seriesIndex: 0, inRange: { color: [...SK_CHART.scale] }
  },
  series: [
    { type: 'scatter', symbolSize: 14, data: measuredPoints.value },
    { type: 'scatter', symbol: 'circle', symbolSize: 26, data: outlierPoints.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.bad, borderWidth: 2 }, silent: true },
    { type: 'scatter', symbol: 'pin', symbolSize: 1, data: failurePoints.value,
      label: { show: true, formatter: '✕', color: SK_CHART.bad, fontSize: 14, fontWeight: 'bold' } },
    { type: 'scatter', symbol: 'circle', symbolSize: 20, data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 }, silent: true, z: 5 }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })
</script>
```

- [ ] **Step 2: Wire the wrapper**

Replace the `<EbeamSkewvoirWaferMap … />` usage in `front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue` with:

```vue
    <EbeamSkewvoirWaferMap
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :focused-sequence="analysis.focusedSequence.value"
      @focus="analysis.setFocusedSequence"
    />
```

Then update the wrapper's `<template>` legend by adding, just below the chart panel's meta area is not needed — the legend lives in Task 10's layout. No script change needed in the wrapper beyond the binding above.

- [ ] **Step 3: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 4: Verify live**

Use the `verify` skill. On a cd-sem analysis link confirm: measured chips are colored, failures show a red `✕`, outlier chips have a red ring `◎`, and clicking any chip draws a blue focus ring (and — after Task 9 — highlights the matching row/SEM). Switching parameters re-renders markers.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/WaferMap.vue
git commit -m "feat(skewvoir): wafer map shows failures ✕ + outlier ◎, click-to-focus (B1 §9.2/§10.1)"
```

---

## Task 6: `Acquisition.vue` → 측정 조건 & 정렬

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/Acquisition.vue`

**Interfaces:**
- Consumes: `analysis.focusFile.value.exe_detail_info`, `.alignment`, and a representative row from `analysis.siteRows`.

- [ ] **Step 1: Rewrite Acquisition to read exe_detail_info + alignment**

Replace the entire file with:

```vue
<template>
  <EbeamSkewvoirPanelFrame title="측정 조건 & 정렬" :meta="meta" icon="i-lucide-settings-2">
    <div class="grid gap-3 md:grid-cols-2">
      <dl class="space-y-1.5 text-[11.5px]">
        <div v-for="f in conditionFields" :key="f.label" class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1">
          <dt class="text-(--sk-ink-muted)">{{ f.label }}</dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">{{ f.value }}</dd>
        </div>
      </dl>
      <div class="space-y-1.5 text-[11.5px]">
        <div v-for="a in alignRows" :key="a.key" class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1">
          <dt class="font-mono text-(--sk-ink-muted)">{{ a.key }}</dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
            {{ a.method }} · {{ a.offset }} <span class="text-(--sk-ink-subtle)">[{{ a.score }}]</span>
          </dd>
        </div>
        <p class="pt-0.5 font-mono text-[10px] text-(--sk-ink-subtle)">score: 모니터링만 · 비교 불가</p>
      </div>
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const info = computed(() => props.analysis.focusFile.value?.exe_detail_info ?? null)
// Representative measurement conditions: mag/vac/pixel are constant across a run,
// so the first measured row for the active parameter is representative.
const cond = computed(() =>
  measuredRows(props.analysis.siteRows.value).find(r => r.parameter === props.analysis.activeParam.value) ?? null
)

const conditionFields = computed(() => [
  { label: 'Wafer', value: info.value?.wafer_id ?? '—' },
  { label: 'Process', value: info.value?.process ?? '—' },
  { label: 'Mag', value: cond.value ? `${cond.value.meas_condition_mag.toLocaleString()} ×` : '—' },
  { label: 'Vacc', value: cond.value ? `${cond.value.meas_condition_vac} V` : '—' },
  { label: 'Pixel', value: cond.value?.meas_condition_pixel ?? '—' }
])

// alignment.offset is keyed (e.g. '1'/'2'/'3') → [method, x, y]; score is keyed the same.
const alignRows = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  if (!a) return []
  return Object.entries(a.offset).map(([key, tuple]) => ({
    key: `ALIGN ${key}`,
    method: tuple[0],
    offset: `${tuple[1]}, ${tuple[2]}`,
    score: a.score[key] ?? '—'
  }))
})

const meta = computed(() => props.analysis.focusFile.value?.exe_detail_info?.recipe_name ?? '—')
</script>
```

- [ ] **Step 2: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 3: Verify live**

Use the `verify` skill. Confirm the panel now shows Wafer / Process / Mag / Vacc / Pixel on the left and ALIGN 1–3 (method · offset · [score]) on the right, with the "score: 모니터링만 · 비교 불가" note.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/Acquisition.vue
git commit -m "feat(skewvoir): Acquisition → 측정 조건 & 정렬 (exe_detail_info + alignment) (B1 §9.2)"
```

---

## Task 7: `overview/VerdictStrip.vue`

**Files:**
- Create: `front-dev-home/app/components/ebeam/skewvoir/overview/VerdictStrip.vue`

**Interfaces:**
- Consumes: `analysis.activeOverview`, `analysis.activeParam`, `analysis.activeUnit`, `analysis.activeSummary`, `analysis.focusFile`.

- [ ] **Step 1: Create the verdict strip (4 cards)**

Create `front-dev-home/app/components/ebeam/skewvoir/overview/VerdictStrip.vue`:

```vue
<template>
  <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
    <!-- 측정 성공률 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">측정 성공률 · COVERAGE</p>
      <p class="mt-1 font-mono text-2xl font-bold tabular-nums" :class="cov.failed > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'">
        {{ cov.measured }} <span class="text-(--sk-ink-subtle)">/ {{ cov.total }}</span>
      </p>
      <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">{{ cov.failed }} 실패 — {{ failPct }}</p>
    </div>

    <!-- 이상 사이트 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">이상 사이트 · OUTLIER SITES</p>
      <template v-if="ov.status === 'evaluated'">
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums" :class="ov.outlierCount > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'">{{ ov.outlierCount }}</p>
        <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">형제 사이트 대비 · leave-one-out</p>
      </template>
      <template v-else>
        <p class="mt-1 font-mono text-lg font-semibold text-(--sk-ink-subtle)">평가 불가</p>
        <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">측정 site 부족</p>
      </template>
    </div>

    <!-- {param} 평균 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="truncate font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">{{ param }} 평균 · MEAN</p>
      <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
        {{ summary ? summary.mean.toFixed(2) : '—' }} <span class="text-[11px] text-(--sk-ink-subtle)">{{ unit }}</span>
      </p>
      <p v-if="summary" class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">
        3Σ {{ (summary.std * 3).toFixed(2) }} · {{ summary.min.toFixed(1) }} – {{ summary.max.toFixed(1) }}
      </p>
    </div>

    <!-- 정렬 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">정렬 · ALIGNMENT</p>
      <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
        {{ align.total }} <span class="text-(--sk-ink-subtle)">/ {{ align.total }}</span>
      </p>
      <p class="mt-0.5 truncate font-mono text-[10.5px] text-(--sk-ink-muted)">{{ align.methods.join(' · ') || '—' }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const ov = computed(() => props.analysis.activeOverview.value)
const cov = computed(() => ov.value.coverage)
const failPct = computed(() => cov.value.total ? `${((cov.value.failed / cov.value.total) * 100).toFixed(1)}%` : '—')
const param = computed(() => props.analysis.activeParam.value)
const unit = computed(() => props.analysis.activeUnit.value)
const summary = computed(() => props.analysis.activeSummary.value)
const align = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  const methods = a ? Object.values(a.offset).map(o => o[0]) : []
  return { total: methods.length, methods }
})
</script>
```

- [ ] **Step 2: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS. (The component isn't rendered until Task 10, so no live verify yet — Task 10 verifies it in the assembled layout.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/overview/VerdictStrip.vue
git commit -m "feat(skewvoir): add VerdictStrip — coverage/outlier/mean/alignment cards (B1 §9.1)"
```

---

## Task 8: `overview/SiteVerdicts.vue` — 이상·실패 사이트 table

**Files:**
- Create: `front-dev-home/app/components/ebeam/skewvoir/overview/SiteVerdicts.vue`

**Interfaces:**
- Consumes: `analysis.activeOverview.value.tableRows`, `analysis.focusedSequence`, `analysis.setFocusedSequence`, `analysis.activeUnit`.

- [ ] **Step 1: Create the site-verdicts table**

Create `front-dev-home/app/components/ebeam/skewvoir/overview/SiteVerdicts.vue`:

```vue
<template>
  <EbeamSkewvoirPanelFrame title="이상 / 실패 사이트" :meta="meta" icon="i-lucide-alert-triangle">
    <div v-if="tableRows.length" class="overflow-auto">
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">SEQ</th>
            <th class="px-2 py-1.5 font-medium">CHIP</th>
            <th class="px-2 py-1.5 text-right font-medium">CD ({{ unit }})</th>
            <th class="px-2 py-1.5 text-right font-medium">Δ vs sites</th>
            <th class="px-2 py-1.5 text-right font-medium">판정</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in tableRows"
            :key="r.sequence"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="[
              r.kind === 'failed' ? 'text-(--sk-ink-subtle)' : '',
              r.sequence === analysis.focusedSequence.value ? 'bg-(--sk-brand)/12' : 'hover:bg-(--sk-chip-bg)'
            ]"
            @click="analysis.setFocusedSequence(r.sequence)"
          >
            <td class="px-2 py-1.5 font-mono">{{ r.sequence }}</td>
            <td class="px-2 py-1.5 font-mono">{{ r.chip }}</td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ r.cd != null ? r.cd.toFixed(2) : '—' }}</td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ r.delta != null ? `${r.delta > 0 ? '+' : ''}${r.delta.toFixed(1)}%` : '—' }}</td>
            <td class="px-2 py-1.5 text-right">
              <span class="rounded-(--sk-r-chip) px-1.5 py-0.5 font-mono text-[10px]" :class="badgeClass(r.kind)">{{ badgeLabel(r.kind) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="px-2 pt-2 font-mono text-[10px] text-(--sk-ink-subtle)">실패 사이트는 통계에서 제외됩니다 — 평균·σ·3Σ 어디에도 포함되지 않습니다.</p>
    </div>
    <div v-else class="flex h-40 items-center justify-center text-[12px] text-(--sk-ink-subtle)">
      {{ analysis.activeOverview.value.status === 'evaluated' ? '이상·실패 사이트가 없습니다.' : '측정 site 부족 — 이상 평가 불가' }}
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SiteKind } from '~/utils/overview'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const tableRows = computed(() => props.analysis.activeOverview.value.tableRows)
const unit = computed(() => props.analysis.activeUnit.value)
const meta = computed(() => `${tableRows.value.length} sites`)

const badgeLabel = (kind: SiteKind) => (kind === 'abnormal' ? '이상' : kind === 'watch' ? '주의' : '측정 실패')
const badgeClass = (kind: SiteKind) =>
  kind === 'abnormal' ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
    : kind === 'watch' ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-(--sk-chip-bg) text-(--sk-ink-subtle)'
</script>
```

- [ ] **Step 2: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/overview/SiteVerdicts.vue
git commit -m "feat(skewvoir): add SiteVerdicts table — flagged + failed sites, click-to-focus (B1 §9.1/§10.1)"
```

---

## Task 9: Linked selection consumers — MeasurementPoints, SemImage, RadiusChart

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/SemImage.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue`

**Interfaces:**
- All consume `analysis.focusedSequence` / `analysis.setFocusedSequence`. `RadiusChart` gains `focusedSequence` prop + `focus` emit, wired through `RadiusPlot`.

- [ ] **Step 1: MeasurementPoints — click row to focus, highlight focused**

In `MeasurementPoints.vue`, make each `<tr>` clickable and highlighted. Replace the `<tr v-for="p in points" …>` opening tag with:

```vue
          <tr
            v-for="p in points"
            :key="p.key"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="p.seq === analysis.focusedSequence.value ? 'bg-(--sk-brand)/12' : 'hover:bg-(--sk-chip-bg)'"
            @click="analysis.setFocusedSequence(p.seq)"
          >
```

- [ ] **Step 2: SemImage — show the focused sequence's image**

In `SemImage.vue`, replace the `images` computed so a focused sequence pins its own image first:

```ts
const images = computed(() => {
  const rows = measuredRows(props.analysis.siteRows.value).filter(r => r.parameter === props.analysis.activeParam.value)
  const focused = props.analysis.focusedSequence.value
  const ordered = focused != null
    ? [...rows].sort((a, b) => (a.sequence === focused ? -1 : 0) - (b.sequence === focused ? -1 : 0))
    : rows
  const seen = new Set<string>()
  const out: string[] = []
  for (const r of ordered) {
    const name = r.mp_image_name_01
    if (name && !seen.has(name)) { seen.add(name); out.push(name) }
  }
  return out
})
```

Also update the meta line to show the focused sequence when set:

```ts
const meta = computed(() => {
  const seq = props.analysis.focusedSequence.value
  return seq != null ? `seq ${seq}` : (images.value[0] ?? `${images.value.length} images`)
})
```

- [ ] **Step 3: RadiusChart — highlight focused point + click to focus**

Add to `RadiusChart.vue` props a `focusedSequence: number | null` and `emit('focus', sequence)`, give scatter points `name = String(sequence)`, add an overlay series for the focused point, and pass `{ onClick: name => emit('focus', Number(name)) }` to `useEchart`. Concretely: add `focusedSequence: number | null` to `defineProps`, add `const emit = defineEmits<{ focus: [sequence: number] }>()`, ensure the scatter `data` entries are `{ name: String(row.sequence), value: [radius, cd] }`, append a highlight series `{ type: 'scatter', symbolSize: 16, data: focusPoint.value, itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 }, silent: true, z: 5 }` where `focusPoint` filters the points to `Number(name) === props.focusedSequence`, and change the `useEchart(chartEl, option)` call to `useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })`. Import `SK_CHART` from `~/utils/chartPalette` if not already imported.

- [ ] **Step 4: RadiusPlot — pass focus through**

In `RadiusPlot.vue`, bind the new props on `<EbeamSkewvoirRadiusChart>`:

```vue
    <EbeamSkewvoirRadiusChart
      v-else-if="hasData"
      :rows="analysis.siteRows.value"
      :parameter="analysis.activeParam.value"
      :unit="analysis.activeUnit.value"
      :degree="degree"
      :focused-sequence="analysis.focusedSequence.value"
      @focus="analysis.setFocusedSequence"
    />
```

- [ ] **Step 5: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 6: Verify live (linked selection end-to-end)**

Use the `verify` skill. On a cd-sem analysis link: click a wafer chip → the Measurement Points row highlights, the Radius point highlights, and the SEM Image switches to that sequence. Click a Measurement Points row → the wafer + radius focus rings move. Confirm focus resets when switching parameter or opening a different MSR.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/SemImage.vue front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue
git commit -m "feat(skewvoir): linked selection across wafer/radius/points/SEM via focusedSequence (B1 §10.1)"
```

---

## Task 10: Assemble the Option A layout in `views/Dashboard.vue`

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue`

**Interfaces:**
- Consumes: all panels above via the `analysis` prop.

- [ ] **Step 1: Rewrite Dashboard.vue with the answer-first layout**

Replace the entire file with:

```vue
<template>
  <div class="space-y-3">
    <!-- Verdict strip — follows the active parameter -->
    <EbeamSkewvoirOverviewVerdictStrip :analysis="analysis" />

    <!-- Parameter navigator — the per-parameter summary; pick the active param -->
    <EbeamSkewvoirDashboardDataSummary :analysis="analysis" />

    <!-- Inspection zone — all linked by focusedSequence -->
    <div class="grid grid-cols-1 gap-3 xl:grid-cols-12">
      <EbeamSkewvoirDashboardWaferMap class="xl:col-span-5" :analysis="analysis" />

      <div class="flex flex-col gap-3 xl:col-span-7">
        <EbeamSkewvoirOverviewSiteVerdicts :analysis="analysis" />
        <EbeamSkewvoirDashboardDistribution :analysis="analysis" />
      </div>

      <EbeamSkewvoirDashboardRadiusPlot class="xl:col-span-5" :analysis="analysis" />
      <EbeamSkewvoirDashboardMeasurementPoints class="xl:col-span-4" :analysis="analysis" />
      <EbeamSkewvoirDashboardSemImage class="xl:col-span-3" :analysis="analysis" />

      <EbeamSkewvoirDashboardAcquisition class="xl:col-span-12" :analysis="analysis" />
    </div>

    <!-- Wafer map legend -->
    <p class="flex flex-wrap items-center gap-3 px-1 font-mono text-[10.5px] text-(--sk-ink-muted)">
      <span class="inline-flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-full" style="background:#5C86AE" /> 낮음</span>
      <span class="inline-flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-full" style="background:#C75A3C" /> 높음</span>
      <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span> 측정 실패 (cd_value: null)</span>
      <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">◎</span> 이상 사이트</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{ analysis: SkewvoirAnalysis }>()
</script>
```

- [ ] **Step 2: Typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: PASS.

- [ ] **Step 3: Verify live (full view)**

Use the `verify` skill on both a cd-sem and an hv-sem analysis link. Confirm top-to-bottom: verdict strip (4 cards, follows active param) → parameter navigator → wafer map + site verdicts + distribution + radius + measurement points + SEM + conditions, with linked selection working and the legend present. Switch parameters via the navigator and confirm every panel and card updates.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue
git commit -m "feat(skewvoir): assemble 측정 개요 answer-first layout (B1 §9/§10.2)"
```

---

## Self-Review

**Spec coverage (§9, §10.1, §10.2, §11):**
- §9.1 VerdictStrip → Task 7; SiteVerdicts → Task 8; 이상 = abnormal+watch, failures separate → Task 1 (`overviewSites`) + tests.
- §9.2 DataSummary→navigator → Task 4; WaferMap ✕/◎ → Task 5; Acquisition→조건&정렬 → Task 6.
- §9.3 HEALTH deletion → Task 2. §9.4 nav relabel (keep slug) → Task 2. §9.5 single outlier definition + coverage math → Task 1 (tests pin it).
- §10.1 focusedSequence + linked panels → Tasks 3, 5, 8, 9. §10.2 navigator at top → Task 10.
- §11 integrity: evidence families separate (coverage vs alignment vs outliers as distinct cards) → Task 7; 평가 불가 states → Tasks 4/7/8 (`status` branches); 3Σ labeled statistical (not spec) → Tasks 4/7 copy; grain/counts → panel metas; drill-through = linked SEM → Task 9.

**Deferred (correctly NOT in this plan):** vs-PEERS card (B2), 위치 비교/Time-Series adaptation (§10.3), FDC/hardware (§12), center-corrected residual outliers (§9.5 caveat → §10.3).

**Placeholder scan:** none — every code step contains complete code; component behavior gated by typecheck+lint+live verify (codebase has no component-test infra).

**Type consistency:** `overviewSites`/`OverviewSites`/`OverviewSiteRow`/`SiteKind` used identically in Tasks 1, 3, 4, 8. `focusedSequence`/`setFocusedSequence` signatures match across Tasks 3, 5, 8, 9. `useEchart(el, option, { onClick })` matches the real signature (`onClick: (name: string) => void`). `alignment.offset` tuple `[method, x, y]` and `score` keying match `AlignmentInfo`.

**Known caveat carried from spec §9.5:** site leave-one-out can flag normal radial structure; documented, badge reads "형제 사이트 대비"; residual-corrected detection is §10.3 (out of scope here).
