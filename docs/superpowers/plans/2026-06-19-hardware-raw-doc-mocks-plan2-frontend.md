# Hardware Raw-Doc Mocks — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild and extend the CD-SEM/HV-SEM hardware page so it renders the five faithful raw-doc mock services (`bsm`, `reso-center`, `fdc`, `mdc`, `sce`) from the new equipment-first API, and make the page deep-link-ready (pre-select tool + time window from query params) for the future skewvoir credibility loop.

**Architecture:** The page shell (`HardwareView.vue`) keeps its list-rail + service-tab layout but now calls the new path `/{slug}/hardware/{eqp_id}/{service}` with `fab_name`/`start`/`end` query, reads deep-link query params off the route to pre-select the tool and window, and dispatches to one panel component per service. Each panel is a thin presentation layer over a **pure util** (`app/utils/*.ts`, unit-tested with `node:test`) that turns the raw docs/settings into chart-ready shapes. BSM is data-driven: selectors are derived from doc keys (length-16 array → radar, numeric scalar → trend) so new mock keys appear in the UI with no frontend edit.

**Tech Stack:** Nuxt 4 + NuxtUI (U-prefixed components), Vue 3 Composition API (`<script setup>`), ECharts 6 via `useEchart`/`useEchartsTheme`, Tailwind v4, `useAsyncData` + `$fetch`. Tests: Node built-in `node:test` + `node:assert/strict` (Node 24 strips types). Package manager: npm.

## Global Constraints

- **Every `.vue` file: `<template>` block FIRST, then `<script setup lang="ts">`.** (User global rule — note the *existing* `HardwareView.vue` has script-first; new/rewritten files follow template-first.)
- **Auto-import prefixes the folder name.** A file at `components/ebeam/hardware/Foo.vue` is referenced as `<EbeamHardwareFoo>`. NEVER duplicate the prefix in the filename (`hardware/MdcPanel.vue` → `<EbeamHardwareMdcPanel>`, not `HardwareMdcPanel.vue`).
- **Tests are for PURE LOGIC ONLY.** Pure functions live in `app/utils/*.ts` with a sibling `*.test.ts` using `node:test` + `node:assert/strict`. Run with `npm --prefix front-dev-home test` (script `test` = `node --test "app/**/*.test.ts"`). Components are NOT unit-tested — verify them with Playwright MCP (screenshots to `.playwright-mcp/screenshots/<name>.png`).
- **NuxtUI `USelect` items MUST have non-empty string `value`** — an empty-string value 500s the page.
- **Styling:** Tailwind v4 canonical classes; use `--sk-ink` / `--sk-ink-muted` / `--sk-ink-subtle` semantic tokens for text (not raw `text-zinc-*`); surfaces via `--sk-surface` / `--sk-border-soft` etc.; layout capped at `max-w-7xl` (1280 px) — but match the existing `HardwareView` shell which uses `max-w-[1440px]` (keep it as-is; do not widen new panels past the detail column).
- **Split when a `.vue` approaches ~900 lines.** Each panel should stay focused; lift chart sub-views into their own `hardware/*` components.
- **npm only** (bun unavailable). Frontend dir is `front-dev-home/`.
- **Shared API names are verbatim from the backend plan** — do not rename: path `/{tool_slug}/hardware/{eqp_id}/{service}`, query keys `fab_name` / `start` / `end`, service keys `bsm | reso-center | fdc | mdc | sce | bm-pm`, payload fields `docs` / `settings`.
- **Source spellings are deliberate** — `Ellipicity`, `Apature angle factor`. Never "correct" them.

---

## File Structure

| File | Create/Modify | Responsibility |
| --- | --- | --- |
| `front-dev-home/app/composables/useHardwareApi.ts` | Modify | Service-key union, `fabName` rename, `start`/`end`, payload `docs`/`settings`, drop `Bsm*` interfaces, eqp-segment path builder |
| `front-dev-home/app/components/ebeam/HardwareView.vue` | Modify | Add new service tabs, `fabName:` call site, read deep-link query params (eqp_id/start/end), route service keys to panels |
| `front-dev-home/app/utils/beamMetrics.ts` | Create | Pure: from `docs`, derive radar metric keys (len-16 arrays), trend scalar keys, label map, auto radial range |
| `front-dev-home/app/utils/beamMetrics.test.ts` | Create | Unit tests for `beamMetrics.ts` |
| `front-dev-home/app/components/ebeam/hardware/BsmPanel.vue` | Modify (rewrite) | beam_condition filter, two scalar-trend panes, two metric radars, scalar header cards, CSV — reads `docs` |
| `front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue` | Modify | Generic single-scalar time-series (was sharpness/noise dual) |
| `front-dev-home/app/components/ebeam/hardware/BsmRadarChart.vue` | Modify | Generic metric radar (already mostly generic — drop fixed min/max default coupling) |
| `front-dev-home/app/utils/mdcMatrix.ts` | Create | Pure: rows×beam_condition matrix + per-cell deviation-from-selected scaling |
| `front-dev-home/app/utils/mdcMatrix.test.ts` | Create | Unit tests for `mdcMatrix.ts` |
| `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue` | Create | Skew matrix heat-table from `settings` |
| `front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue` | Create | Center-drift scatter + BestReso/ResoDelta trend + focus-sweep curve |
| `front-dev-home/app/utils/fdcValues.ts` | Create | Pure: parse each `fdc_key` `values` list into typed shapes |
| `front-dev-home/app/utils/fdcValues.test.ts` | Create | Unit tests for `fdcValues.ts` |
| `front-dev-home/app/components/ebeam/hardware/FdcPanel.vue` | Create | `fdc_key` sub-tabs (temp trend, laser dual-axis, SPM profile, contactpin table) |
| `front-dev-home/app/utils/sceCompare.ts` | Create | Pure: settings diff across eqp + siblings (flag differing keys) |
| `front-dev-home/app/utils/sceCompare.test.ts` | Create | Unit tests for `sceCompare.ts` |
| `front-dev-home/app/components/ebeam/hardware/ScePanel.vue` | Create | Settings-compare table + Coefficients[0..359] overlay curve |

---

## Task 1: API composable — new path, rename, payload fields

**Files:**
- Modify: `front-dev-home/app/composables/useHardwareApi.ts`

**Interfaces:**
- Consumes: `joinApiPath(base, path)` from `~/utils/apiPath`.
- Produces (relied on by every later task):

```ts
export type HardwareServiceKey = 'bsm' | 'reso-center' | 'fdc' | 'mdc' | 'sce' | 'bm-pm'

export interface HardwarePayload {
  tool_slug: 'cdsem' | 'hvsem'
  service: HardwareServiceKey
  eqp_id: string | null
  fab_name: string | null
  available: boolean
  fetched_at: string
  summary: string
  cards: HardwareMetricCard[]
  tables: HardwareTableSection[]
  docs?: Record<string, unknown>[]        // bsm / reso-center / fdc
  settings?: Record<string, Record<string, unknown>>  // mdc / sce (keyed by eqp_id)
  raw?: Record<string, HardwareMetricValue>
}

export interface HardwareQuery {
  toolType: HardwareToolType
  service: HardwareServiceKey
  eqpId?: string
  fabName?: string
  start?: string   // ISO 8601
  end?: string     // ISO 8601
}

// useHardwareApi() returns { fetchService(params: HardwareQuery): Promise<HardwarePayload> }
```

- [ ] **Step 1: Extend the service-key union and remove the Bsm* types.**

In `useHardwareApi.ts`, change line 4 to:

```ts
export type HardwareServiceKey = 'bsm' | 'reso-center' | 'fdc' | 'mdc' | 'sce' | 'bm-pm'
```

Delete the `BsmSummaryRow`, `BsmProfile`, `BsmCategory`, `BsmBlock`, and `BsmMetric` interfaces/types entirely (current lines 31–60). Keep `HardwareMetricCard`, `HardwareTableColumn`, `HardwareTableSection`.

- [ ] **Step 2: Rewrite `HardwarePayload`.**

Replace the existing `HardwarePayload` interface with:

```ts
export interface HardwarePayload {
  tool_slug: 'cdsem' | 'hvsem'
  service: HardwareServiceKey
  eqp_id: string | null
  fab_name: string | null
  available: boolean
  fetched_at: string
  summary: string
  cards: HardwareMetricCard[]
  tables: HardwareTableSection[]
  // bsm / reso-center / fdc → faithful raw docs (ascending time).
  docs?: Record<string, unknown>[]
  // mdc / sce → dict-of-dict keyed by eqp_id (selected eqp + in-fab siblings).
  settings?: Record<string, Record<string, unknown>>
  raw?: Record<string, HardwareMetricValue>
}
```

- [ ] **Step 3: Rewrite `HardwareQuery` (fabId → fabName, add start/end).**

```ts
export interface HardwareQuery {
  toolType: HardwareToolType
  service: HardwareServiceKey
  eqpId?: string
  fabName?: string
  start?: string
  end?: string
}
```

- [ ] **Step 4: Rebuild the path + query in `fetchService`.**

`eqp_id` becomes a path SEGMENT; `fab_name`/`start`/`end` are query. When `eqpId` is missing, fall back to the literal `_` segment so the URL stays well-formed (the page always has a selected tool in practice, but this keeps the call total):

```ts
const fetchService = async (params: HardwareQuery): Promise<HardwarePayload> => {
  const query: Record<string, string> = {}
  if (params.fabName) query.fab_name = params.fabName
  if (params.start) query.start = params.start
  if (params.end) query.end = params.end

  const eqpSegment = params.eqpId ?? '_'
  return await $fetch<HardwarePayload>(
    joinApiPath(base, `/${toolSlug(params.toolType)}/hardware/${eqpSegment}/${params.service}`),
    { query }
  )
}
```

- [ ] **Step 5: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS for this file (errors WILL remain in `HardwareView.vue` / `BsmPanel.vue` referencing the dropped types — those are fixed in Tasks 2 and 4; note them and proceed).

- [ ] **Step 6: Commit.**

```bash
git add front-dev-home/app/composables/useHardwareApi.ts
git commit -m "feat(hardware): new eqp-segment path + docs/settings payload, drop Bsm* types"
```

---

## Task 2: HardwareView — service tabs, fabName, deep-link params, panel routing

**Files:**
- Modify: `front-dev-home/app/components/ebeam/HardwareView.vue`

**Interfaces:**
- Consumes: `HardwarePayload`, `HardwareServiceKey`, `HardwareQuery` (Task 1); the panel components `<EbeamHardwareBsmPanel :docs :fetched-at>` (Task 4), `<EbeamHardwareResoCenterPanel :docs>` (Task 6), `<EbeamHardwareFdcPanel :docs>` (Task 7), `<EbeamHardwareMdcPanel :settings :selected-eqp>` (Task 5), `<EbeamHardwareScePanel :settings :selected-eqp>` (Task 8); `useRoute()` for deep-link query.
- Produces: passes `:docs="servicePayload.docs"`, `:settings="servicePayload.settings"`, `:selected-eqp="selectedTool?.eqp_id"`, `:fetched-at="servicePayload.fetched_at"` to panels.

- [ ] **Step 1: Add the four new service tabs to `hardwareServices`.**

After the existing `bsm` entry and before `fdc`, and after `fdc`, insert `reso-center`, `mdc`, `sce` so the array reads (keep `bm-pm` first as default):

```ts
const hardwareServices: HardwareService[] = [
  { key: 'bm-pm', label: 'BM/PM', title: 'BM / PM Information', description: '장비별 BM 이력, PM 일정, maintenance window를 함께 확인합니다.', icon: 'i-lucide-wrench' },
  { key: 'bsm', label: 'BSM', title: 'Beam Shape Matching', description: '장비 상태를 나타내는 지표 중 하나인 Beam Shape을 모니터링 합니다.', icon: 'i-lucide-radar' },
  { key: 'reso-center', label: 'Reso Center', title: 'Resolution Center', description: 'Resolution center drift와 focus sweep를 추적합니다.', icon: 'i-lucide-crosshair' },
  { key: 'fdc', label: 'FDC', title: 'Fault Detection & Classification', description: '실시간 fault signal, alarm trend, classification 상태를 장비 단위로 확인합니다.', icon: 'i-lucide-activity' },
  { key: 'mdc', label: 'MDC', title: 'Meas Data Correction', description: '장비별 MDC 보정값을 비교하여 tool-to-tool skew를 확인합니다.', icon: 'i-lucide-grid-3x3' },
  { key: 'sce', label: 'SCE', title: 'Sharpness Characteristic Equalizer', description: 'SCE 설정값과 Coefficient 곡선을 sibling 장비와 비교합니다.', icon: 'i-lucide-spline' }
]
```

- [ ] **Step 2: Read deep-link query params and seed selection + window.**

Right after `const { fetchService } = useHardwareApi()` (line 53), add:

```ts
const route = useRoute()

// Deep-link contract (spec §4): /ebeam/cd-sem/<fab>/hardware?eqp_id=&start=&end=
// Pre-select the tool and set the time window from the URL on first load.
const qp = (k: string): string => {
  const v = route.query[k]
  return Array.isArray(v) ? (v[0] ?? '') : (v ?? '')
}
const deepLinkEqpId = qp('eqp_id')

// 30-day default window when start/end omitted (spec §3, §13).
const DAY_MS = 86_400_000
const defaultEnd = new Date()
const defaultStart = new Date(defaultEnd.getTime() - 30 * DAY_MS)
const toIso = (d: Date) => d.toISOString()
const windowStart = ref(qp('start') || toIso(defaultStart))
const windowEnd = ref(qp('end') || toIso(defaultEnd))
```

Then change the initial selected-tool seed (line 62) so a deep-link `eqp_id` wins over the store value:

```ts
const selectedToolId = ref(deepLinkEqpId || storeSelectedToolId.value)
```

Leave the existing `if (storeSelectedToolId.value) setSelectedTool('')` clear-after-consume block as-is.

- [ ] **Step 3: Pass `fabName` / `start` / `end` at the fetch call site.**

Replace the `fetchService({...})` body inside `useAsyncData` (lines 164–169) with:

```ts
() => fetchService({
  toolType: props.toolType,
  service: activeService.value,
  eqpId: selectedTool.value?.eqp_id,
  fabName: selectedTool.value?.fab_name,
  start: windowStart.value,
  end: windowEnd.value
}),
```

(The `watch` array on line 171 keeps working; `windowStart`/`windowEnd` are set once on load and don't need to be watched this round.)

- [ ] **Step 4: Replace the BSM panel usage and add the four new panel mounts.**

Remove the old `<EbeamHardwareBsmPanel v-if="activeService === 'bsm' && servicePayload.bsm" :bsm="servicePayload.bsm" />` block (lines 435–439). In its place, render the doc/settings-driven panels (keep the existing BM/PM tables block and the generic-table `v-for`, but exclude the new services from the generic table loop):

```vue
<!-- BSM: beam_condition filter + scalar trends + 360° radars (reads docs) -->
<EbeamHardwareBsmPanel
  v-if="activeService === 'bsm'"
  :docs="servicePayload.docs ?? []"
  :fetched-at="servicePayload.fetched_at"
/>

<!-- Reso Center: drift scatter + best-reso trend + focus sweep -->
<EbeamHardwareResoCenterPanel
  v-else-if="activeService === 'reso-center'"
  :docs="servicePayload.docs ?? []"
/>

<!-- FDC: fdc_key sub-tabs -->
<EbeamHardwareFdcPanel
  v-else-if="activeService === 'fdc'"
  :docs="servicePayload.docs ?? []"
/>

<!-- MDC: skew matrix -->
<EbeamHardwareMdcPanel
  v-else-if="activeService === 'mdc'"
  :settings="servicePayload.settings ?? {}"
  :selected-eqp="selectedTool?.eqp_id ?? ''"
/>

<!-- SCE: settings compare + coefficient curve -->
<EbeamHardwareScePanel
  v-else-if="activeService === 'sce'"
  :settings="servicePayload.settings ?? {}"
  :selected-eqp="selectedTool?.eqp_id ?? ''"
/>
```

Then change the generic-table `v-for` source (line 443) so only `bm-pm` is excluded but the new panel services don't double-render an empty table — restrict it to services that still use raw tables (`fdc` contactpin and any tabular section come through their own panels now, so render the generic table only when no dedicated panel handles the service):

```vue
v-for="section in (['bm-pm','bsm','reso-center','fdc','mdc','sce'].includes(activeService) ? [] : servicePayload.tables)"
```

- [ ] **Step 5: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: errors only for the not-yet-created panel components and the still-old `BsmPanel.vue` (fixed in later tasks). The `HardwareView.vue` logic itself should be type-clean.

- [ ] **Step 6: Commit.**

```bash
git add front-dev-home/app/components/ebeam/HardwareView.vue
git commit -m "feat(hardware): add 4 service tabs, fabName + deep-link window, panel routing"
```

---

## Task 3: `beamMetrics` util (TDD) — data-driven BSM selectors

**Files:**
- Create: `front-dev-home/app/utils/beamMetrics.ts`
- Test: `front-dev-home/app/utils/beamMetrics.test.ts`

**Interfaces:**
- Consumes: nothing (pure).
- Produces (used by Task 4):

```ts
export interface BeamMetricOption { key: string; label: string }
export function profileMetricKeys(docs: Record<string, unknown>[]): BeamMetricOption[]
export function scalarMetricKeys(docs: Record<string, unknown>[]): BeamMetricOption[]
export function radialRange(docs: Record<string, unknown>[], key: string): { min: number; max: number }
export function degreeLabels(docs: Record<string, unknown>[]): string[]
export function prettyLabel(key: string): string
export const BEAM_LABELS: Record<string, string>
```

Rules:
- A key is a **profile (radar) metric** when its value is an array of exactly 16 finite numbers in the FIRST doc that has the key. (`degree` and `Reso EB Focus Range` are excluded by an explicit deny-list.)
- A key is a **scalar (trend) metric** when its value is a finite number (or numeric string) in the first doc that has it. (Metadata keys `eqp_ip` etc. are non-numeric and naturally excluded.)
- `radialRange` scans every doc's array for `key`, finds global min/max across all 16×N points, pads by 5 % of the span (min 0.001 pad), returns `{min, max}` rounded to 6 dp. Empty → `{min: 0, max: 1}`.
- `degreeLabels` returns the `degree` array of the first doc as strings (`['0','22.5',…]`), or 16 fallback labels `0,22.5,…337.5` if absent.
- Numeric strings ARE numbers: `toNum('8.066')` → `8.066`; `toNum('total')` → `NaN`.

- [ ] **Step 1: Write the failing test.**

Create `front-dev-home/app/utils/beamMetrics.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  profileMetricKeys, scalarMetricKeys, radialRange, degreeLabels, prettyLabel,
  type BeamMetricOption
} from './beamMetrics.ts'

const arr16 = (base: number) => Array.from({ length: 16 }, (_, i) => base + i * 0.01)

const doc = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  'degree': [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5],
  'Reso EB': arr16(8.0),
  'Reso Detector': arr16(0.005),
  'Reso EB Focus Range': ['8.0000'],
  'Ellipicity': 1.023,
  'Major Axis': 8.12,
  'Ave. Noise': '6.277',          // numeric string scalar
  'type': 'total',
  'beam_condition': 'HR0800_IP0080',
  'eqp_id': 'ECXDX1234',
  ...overrides
})

test('profileMetricKeys: only length-16 numeric arrays, degree + Focus Range excluded', () => {
  const keys = profileMetricKeys([doc()]).map(o => o.key).sort()
  assert.deepEqual(keys, ['Reso Detector', 'Reso EB'])
})

test('profileMetricKeys: rejects a short array', () => {
  const keys = profileMetricKeys([doc({ 'Reso EB': [1, 2, 3] })]).map(o => o.key)
  assert.ok(!keys.includes('Reso EB'))
})

test('scalarMetricKeys: numbers and numeric strings, no arrays/metadata', () => {
  const keys = scalarMetricKeys([doc()]).map(o => o.key).sort()
  assert.deepEqual(keys, ['Ave. Noise', 'Ellipicity', 'Major Axis'])
})

test('radialRange: global min/max across docs, padded, never zero span', () => {
  const r = radialRange([doc({ 'Reso EB': arr16(8.0) }), doc({ 'Reso EB': arr16(9.0) })], 'Reso EB')
  // values span 8.00 .. 9.15 → padded outward
  assert.ok(r.min < 8.0)
  assert.ok(r.max > 9.15)
})

test('radialRange: missing key → {0,1}', () => {
  assert.deepEqual(radialRange([doc()], 'Nope'), { min: 0, max: 1 })
})

test('degreeLabels: first doc degree as strings', () => {
  assert.deepEqual(degreeLabels([doc()])[1], '22.5')
})

test('prettyLabel: keeps source spellings verbatim when unknown', () => {
  assert.equal(prettyLabel('Apature angle factor'), 'Apature angle factor')
})
```

- [ ] **Step 2: Run to verify it fails.**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './beamMetrics.ts'`.

- [ ] **Step 3: Implement `beamMetrics.ts`.**

Create `front-dev-home/app/utils/beamMetrics.ts`:

```ts
// Pure helpers that derive BSM panel selectors straight off the faithful
// beam_shape docs — no per-key frontend edits (spec §7.1). A doc key whose
// value is a length-16 numeric array is a radar metric; a numeric scalar is a
// trend metric. Adding a future key to the mock surfaces it automatically.

export interface BeamMetricOption { key: string; label: string }

// Keys that look like profile arrays but are NOT selectable metrics.
const PROFILE_DENY = new Set(['degree', 'Reso EB Focus Range'])

// Prettify known keys; unknown keys fall through verbatim (source spellings
// like "Ellipicity" / "Apature angle factor" are intentional).
export const BEAM_LABELS: Record<string, string> = {
  'Reso EB': 'Reso EB',
  'Reso Detector': 'Reso Detector',
  'Noise': 'Noise',
  'Focus offset': 'Focus offset',
  'Apature angle factor': 'Apature angle factor',
  'Reso EB Focus': 'Reso EB Focus',
  'Ellipicity': 'Ellipicity',
  'Major Axis': 'Major Axis',
  'Minor Axis': 'Minor Axis',
  'Tilt': 'Tilt',
  'X range': 'X range',
  'Y range': 'Y range',
  'Area': 'Area',
  'Ave. Reso Detector': 'Ave. Reso Detector',
  'Ave. Noise': 'Ave. Noise',
  'Ave. Apature angle factor': 'Ave. Apature angle factor'
}

export const prettyLabel = (key: string): string => BEAM_LABELS[key] ?? key

const toNum = (v: unknown): number => {
  if (typeof v === 'number') return v
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    return Number.isFinite(n) ? n : NaN
  }
  return NaN
}

const isLen16NumberArray = (v: unknown): v is unknown[] =>
  Array.isArray(v) && v.length === 16 && v.every(x => Number.isFinite(toNum(x)))

const isScalarNumber = (v: unknown): boolean =>
  (typeof v === 'number' || typeof v === 'string') && Number.isFinite(toNum(v))

const option = (key: string): BeamMetricOption => ({ key, label: prettyLabel(key) })

// Use the first doc that actually owns each key to classify it.
const classify = (docs: Record<string, unknown>[]): { profile: Set<string>; scalar: Set<string> } => {
  const profile = new Set<string>()
  const scalar = new Set<string>()
  for (const d of docs) {
    for (const [k, v] of Object.entries(d)) {
      if (profile.has(k) || scalar.has(k)) continue
      if (!PROFILE_DENY.has(k) && isLen16NumberArray(v)) profile.add(k)
      else if (!Array.isArray(v) && isScalarNumber(v)) scalar.add(k)
    }
  }
  return { profile, scalar }
}

export const profileMetricKeys = (docs: Record<string, unknown>[]): BeamMetricOption[] =>
  [...classify(docs).profile].sort().map(option)

export const scalarMetricKeys = (docs: Record<string, unknown>[]): BeamMetricOption[] =>
  [...classify(docs).scalar].sort().map(option)

export const radialRange = (
  docs: Record<string, unknown>[],
  key: string
): { min: number; max: number } => {
  let lo = Infinity
  let hi = -Infinity
  for (const d of docs) {
    const v = d[key]
    if (!Array.isArray(v)) continue
    for (const cell of v) {
      const n = toNum(cell)
      if (!Number.isFinite(n)) continue
      if (n < lo) lo = n
      if (n > hi) hi = n
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return { min: 0, max: 1 }
  const span = hi - lo
  const pad = Math.max(span * 0.05, 0.001)
  const round6 = (n: number) => Number(n.toFixed(6))
  return { min: round6(lo - pad), max: round6(hi + pad) }
}

export const degreeLabels = (docs: Record<string, unknown>[]): string[] => {
  const first = docs.find(d => Array.isArray(d.degree))
  if (first && Array.isArray(first.degree)) return (first.degree as unknown[]).map(String)
  return Array.from({ length: 16 }, (_, i) => String(i * 22.5))
}
```

- [ ] **Step 4: Run to verify pass.**

Run: `npm --prefix front-dev-home test`
Expected: PASS (all `beamMetrics` tests green).

- [ ] **Step 5: Commit.**

```bash
git add front-dev-home/app/utils/beamMetrics.ts front-dev-home/app/utils/beamMetrics.test.ts
git commit -m "feat(hardware): beamMetrics util — data-driven BSM selectors (TDD)"
```

---

## Task 4: Rebuild BSM panel + generic charts (reads docs)

**Files:**
- Modify (rewrite): `front-dev-home/app/components/ebeam/hardware/BsmPanel.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/BsmRadarChart.vue`

**Interfaces:**
- Consumes: `profileMetricKeys`, `scalarMetricKeys`, `radialRange`, `degreeLabels`, `prettyLabel` (Task 3); `downloadCsv` from `~/utils/csvDownload`; `useEchart` / `useEchartsTheme`.
- Props received from `HardwareView`: `docs: Record<string, unknown>[]`, `fetchedAt: string`.
- Produces (chart child contracts):
  - `<EbeamHardwareBsmTrendChart :label :points :selected @select>` where `points: { ts: string; value: number }[]`, `selected: string`, emit `select: [ts: string]`.
  - `<EbeamHardwareBsmRadarChart :title :angles :values :min :max :color-index>`.

- [ ] **Step 1: Rewrite `BsmTrendChart.vue` to a single generic scalar series.**

Replace the whole file with (template first):

```vue
<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="text-[11px] font-semibold uppercase tracking-[0.06em] text-(--sk-ink-muted)">
        {{ label }}
      </span>
    </div>
    <div
      v-if="points.length === 0"
      class="flex h-72 items-center justify-center text-sm text-(--sk-ink-muted)"
    >
      추세 데이터가 없습니다.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  label: string
  points: { ts: string; value: number }[]
  selected: string
}>()

const emit = defineEmits<{ select: [ts: string] }>()

const chartEl = ref<HTMLDivElement | null>(null)
const { palette } = useEchartsTheme()
const color = computed(() => palette.value[0] ?? '#C75A3C')

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()
const formatTime = (value: number | string) => {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}/${dd} ${hh}:${mi}`
}

// Points arrive ascending (oldest first) from the panel.
const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 16, top: 16, bottom: 56 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'line' },
    valueFormatter: v => (typeof v === 'number' ? v.toFixed(4) : String(v))
  },
  xAxis: { type: 'time', axisLabel: { fontSize: 10, formatter: formatTime } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 16, bottom: 12 }
  ],
  series: [
    {
      type: 'line',
      showSymbol: true,
      lineStyle: { color: color.value, width: 1.8 },
      itemStyle: { color: color.value },
      emphasis: { scale: 1.6 },
      data: props.points.map(p => ({
        name: p.ts,
        value: [toEpoch(p.ts), p.value],
        symbolSize: p.ts === props.selected ? 12 : 5
      }))
    }
  ]
}))

useEchart(chartEl, chartOption, { onClick: ts => emit('select', ts) })
</script>
```

- [ ] **Step 2: Generalize `BsmRadarChart.vue`.**

The file is already metric-generic (props `title`/`angles`/`values`/`min`/`max`/`colorIndex`). No structural change needed, but confirm it does NOT import any dropped type. Open it and verify there is no `import type { Bsm... }` line (there isn't). Leave as-is. (No commit for an unchanged file.)

- [ ] **Step 3: Rewrite `BsmPanel.vue` to read `docs`.**

Replace the whole file with (template first):

```vue
<template>
  <div class="mt-3 space-y-3">
    <!-- Filter row: beam_condition -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-(--sk-ink-muted)">Beam Condition</span>
        <USelect
          v-model="beamCondition"
          :items="beamConditionItems"
          size="xs"
          icon="i-lucide-filter"
          class="w-48"
        />
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ filteredDocs.length }} docs</span>
      </div>
      <UButton
        icon="i-lucide-download"
        size="xs"
        color="neutral"
        variant="outline"
        :disabled="filteredDocs.length === 0"
        @click="downloadScalarsCsv"
      >
        CSV 다운로드
      </UButton>
    </div>

    <!-- Header cards: scalars of the selected measurement -->
    <dl
      v-if="selectedScalarCards.length"
      class="grid gap-x-6 gap-y-2 sm:grid-cols-3 lg:grid-cols-5"
    >
      <div
        v-for="card in selectedScalarCards"
        :key="card.key"
        class="rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)"
      >
        <dt class="truncate font-mono text-[10px] uppercase tracking-[0.05em] text-(--sk-ink-muted)">
          {{ card.label }}
        </dt>
        <dd class="mt-0.5 font-mono text-sm font-bold tabular-nums text-(--sk-ink)">
          {{ card.value }}
        </dd>
      </div>
    </dl>

    <!-- Two stacked scalar trend panes, each its own scalar dropdown -->
    <div class="grid gap-3 lg:grid-cols-2">
      <div
        v-for="pane in trendPanes"
        :key="pane.id"
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
      >
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <USelect
            v-model="pane.metric.value"
            :items="scalarItems"
            size="xs"
            class="w-44"
          />
        </div>
        <EbeamHardwareBsmTrendChart
          :label="prettyLabel(pane.metric.value)"
          :points="trendPoints(pane.metric.value)"
          :selected="selectedTs"
          @select="selectedTs = $event"
        />
      </div>
    </div>

    <!-- Dual 360° radars for the selected measurement -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="text-xs font-bold text-(--sk-ink)">360° 빔 형상</div>
        <USelect
          v-model="selectedTs"
          :items="timestampItems"
          size="xs"
          icon="i-lucide-clock"
          placeholder="측정 시각 선택"
          class="w-56"
        />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div
          v-for="radar in radarPanes"
          :key="radar.id"
          class="flex flex-col"
        >
          <USelect
            v-model="radar.metric.value"
            :items="profileItems"
            size="xs"
            class="mx-auto mb-1 w-44"
          />
          <EbeamHardwareBsmRadarChart
            :title="prettyLabel(radar.metric.value)"
            :color-index="radar.colorIndex"
            :angles="angles"
            :values="profileValues(radar.metric.value)"
            :min="radialRange(filteredDocs, radar.metric.value).min"
            :max="radialRange(filteredDocs, radar.metric.value).max"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  profileMetricKeys, scalarMetricKeys, radialRange, degreeLabels, prettyLabel
} from '~/utils/beamMetrics'
import { downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  docs: Record<string, unknown>[]
  fetchedAt: string
}>()

const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')
const numOf = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}

// beam_condition filter
const beamConditions = computed(() =>
  Array.from(new Set(props.docs.map(d => String(d.beam_condition ?? '')).filter(Boolean))).sort()
)
const beamCondition = ref('all')
const beamConditionItems = computed(() => [
  { label: 'All conditions', value: 'all' },
  ...beamConditions.value.map(c => ({ label: c, value: c }))
])

const filteredDocs = computed(() =>
  beamCondition.value === 'all'
    ? props.docs
    : props.docs.filter(d => String(d.beam_condition ?? '') === beamCondition.value)
)

// Selectors derived from docs (data-driven).
const profileOptions = computed(() => profileMetricKeys(props.docs))
const scalarOptions = computed(() => scalarMetricKeys(props.docs))
const profileItems = computed(() => profileOptions.value.map(o => ({ label: o.label, value: o.key })))
const scalarItems = computed(() => scalarOptions.value.map(o => ({ label: o.label, value: o.key })))
const angles = computed(() => degreeLabels(props.docs))

// Two trend metrics + two radar metrics, seeded from known keys when present.
const pick = (opts: { key: string }[], preferred: string, fallbackIdx: number) =>
  opts.some(o => o.key === preferred) ? preferred : (opts[fallbackIdx]?.key ?? opts[0]?.key ?? '')

const trendA = ref(pick(scalarOptions.value, 'Ellipicity', 0))
const trendB = ref(pick(scalarOptions.value, 'Ave. Noise', 1))
const radarA = ref(pick(profileOptions.value, 'Reso EB', 0))
const radarB = ref(pick(profileOptions.value, 'Reso Detector', 1))

const trendPanes = [
  { id: 'a', metric: trendA },
  { id: 'b', metric: trendB }
]
const radarPanes = [
  { id: 'a', metric: radarA, colorIndex: 0 },
  { id: 'b', metric: radarB, colorIndex: 1 }
]

// Trend points (ascending time) for a scalar key.
const trendPoints = (key: string) =>
  filteredDocs.value
    .map(d => ({ ts: tsOf(d), value: numOf(d[key]) }))
    .filter(p => p.ts && Number.isFinite(p.value))
    .sort((a, b) => a.ts.localeCompare(b.ts))

// Timestamps (desc, newest first) for the radar selector dropdown.
const timestampItems = computed(() =>
  [...filteredDocs.value].map(tsOf).filter(Boolean).sort((a, b) => b.localeCompare(a))
)

const selectedTs = ref('')
watch(timestampItems, (items) => {
  if (!items.includes(selectedTs.value)) selectedTs.value = items[0] ?? ''
}, { immediate: true })

const selectedDoc = computed(() => filteredDocs.value.find(d => tsOf(d) === selectedTs.value))

const profileValues = (key: string): number[] => {
  const v = selectedDoc.value?.[key]
  return Array.isArray(v) ? v.map(numOf) : []
}

const selectedScalarCards = computed(() => {
  const d = selectedDoc.value
  if (!d) return []
  return scalarOptions.value.map(o => ({
    key: o.key,
    label: o.label,
    value: Number.isFinite(numOf(d[o.key])) ? numOf(d[o.key]).toFixed(4) : '-'
  }))
})

const downloadScalarsCsv = () => {
  const keys = scalarOptions.value.map(o => o.key)
  const headers = ['timestamp', 'beam_condition', ...keys]
  const rows = [...filteredDocs.value]
    .sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
    .map(d => [tsOf(d), String(d.beam_condition ?? ''), ...keys.map(k => numOf(d[k]))])
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`bsm-${beamCondition.value}-${date}.csv`, headers, rows)
}
</script>
```

- [ ] **Step 4: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS for the BSM files (panel routing in `HardwareView` now resolves `<EbeamHardwareBsmPanel>`; remaining errors are the 4 not-yet-created panels).

- [ ] **Step 5: Playwright verify.**

Start dev (user usually runs Flask :5050 + Nuxt :3000 in PyCharm; if not running, run `npm --prefix front-dev-home run dev` in the background). Then:

1. `browser_navigate` to `http://localhost:3000/ebeam/cd-sem/m16b/hardware`.
2. Click the **BSM** service pill.
3. Confirm: beam_condition select, two trend panes (each a scalar dropdown), two radars (each a metric dropdown), header scalar cards, CSV button.
4. Click a trend point → the radar timestamp updates.
5. `browser_take_screenshot` → `.playwright-mcp/screenshots/bsm-panel.png`.

- [ ] **Step 6: Commit.**

```bash
git add front-dev-home/app/components/ebeam/hardware/BsmPanel.vue front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue
git commit -m "feat(hardware): rebuild BSM panel on faithful docs (data-driven selectors)"
```

---

## Task 5: `mdcMatrix` util (TDD) + MdcPanel

**Files:**
- Create: `front-dev-home/app/utils/mdcMatrix.ts`
- Test: `front-dev-home/app/utils/mdcMatrix.test.ts`
- Create: `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue`

**Interfaces:**
- Consumes: nothing (pure) for the util; `MdcMatrix` for the panel.
- Produces (used by `MdcPanel`):

```ts
export interface MdcMatrix {
  tools: string[]            // row order; selected eqp first
  conditions: string[]       // column order (union of all beam_condition keys, sorted)
  values: (number | null)[][]   // [row][col]; null when a tool lacks that condition
}
export function buildMdcMatrix(
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): MdcMatrix
// Per-cell deviation vs the SELECTED tool's value for the same column,
// normalized to [-1,1] by the column's max abs deviation. 0 when no baseline.
export function cellDeviation(matrix: MdcMatrix, row: number, col: number): number
```

- [ ] **Step 1: Write the failing test.**

Create `front-dev-home/app/utils/mdcMatrix.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildMdcMatrix, cellDeviation } from './mdcMatrix.ts'

const settings = {
  ECX002: { '800V_HR_0Deg': '1.004', '500V_HR_0Deg': '1.0030' },
  ECX001: { '800V_HR_0Deg': '1.000', '500V_HR_0Deg': '1.0000', '3000V': '0.99' },
  ECX003: { '800V_HR_0Deg': '1.010' }
}

test('buildMdcMatrix: selected eqp is the first row; columns are the sorted union', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  assert.equal(m.tools[0], 'ECX001')
  assert.deepEqual(m.conditions, ['3000V', '500V_HR_0Deg', '800V_HR_0Deg'])
})

test('buildMdcMatrix: missing condition for a tool is null', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const rowECX003 = m.tools.indexOf('ECX003')
  const col3000 = m.conditions.indexOf('3000V')
  assert.equal(m.values[rowECX003]![col3000], null)
})

test('buildMdcMatrix: numeric strings parsed to numbers', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  assert.equal(m.values[0]![col800], 1.0) // ECX001 row
})

test('cellDeviation: selected tool deviates 0 from itself', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  assert.equal(cellDeviation(m, 0, col800), 0)
})

test('cellDeviation: sign follows direction, magnitude in [-1,1]', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  const rowECX003 = m.tools.indexOf('ECX003') // 1.010 vs baseline 1.000 → positive
  const dev = cellDeviation(m, rowECX003, col800)
  assert.ok(dev > 0 && dev <= 1)
})

test('cellDeviation: null cell → 0', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const rowECX003 = m.tools.indexOf('ECX003')
  const col3000 = m.conditions.indexOf('3000V')
  assert.equal(cellDeviation(m, rowECX003, col3000), 0)
})
```

- [ ] **Step 2: Run to verify it fails.**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './mdcMatrix.ts'`.

- [ ] **Step 3: Implement `mdcMatrix.ts`.**

```ts
// Pure: turn the mdc settings dict-of-dict into a tools×beam_condition matrix
// and a per-cell deviation-from-selected scaling for the skew heat-table (§7.4).

export interface MdcMatrix {
  tools: string[]
  conditions: string[]
  values: (number | null)[][]
}

const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export const buildMdcMatrix = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): MdcMatrix => {
  const allTools = Object.keys(settings)
  // Selected eqp first (if present), then the rest in stable sorted order.
  const rest = allTools.filter(t => t !== selectedEqp).sort()
  const tools = settings[selectedEqp] ? [selectedEqp, ...rest] : rest

  const condSet = new Set<string>()
  for (const t of tools) for (const c of Object.keys(settings[t] ?? {})) condSet.add(c)
  const conditions = [...condSet].sort()

  const values = tools.map(t =>
    conditions.map(c => toNum(settings[t]?.[c]))
  )

  return { tools, conditions, values }
}

export const cellDeviation = (matrix: MdcMatrix, row: number, col: number): number => {
  const v = matrix.values[row]?.[col]
  const baseline = matrix.values[0]?.[col] // row 0 = selected tool
  if (v === null || v === undefined || baseline === null || baseline === undefined) return 0

  // Normalize against the column's largest abs deviation so colors are
  // comparable within a column.
  let maxAbs = 0
  for (let r = 0; r < matrix.values.length; r++) {
    const cell = matrix.values[r]?.[col]
    if (cell === null || cell === undefined) continue
    maxAbs = Math.max(maxAbs, Math.abs(cell - baseline))
  }
  if (maxAbs === 0) return 0
  return (v - baseline) / maxAbs
}
```

- [ ] **Step 4: Run to verify pass.**

Run: `npm --prefix front-dev-home test`
Expected: PASS.

- [ ] **Step 5: Commit the util.**

```bash
git add front-dev-home/app/utils/mdcMatrix.ts front-dev-home/app/utils/mdcMatrix.test.ts
git commit -m "feat(hardware): mdcMatrix util — skew matrix + deviation scaling (TDD)"
```

- [ ] **Step 6: Implement `MdcPanel.vue`.**

Create `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue` (template first). Color the cell background by deviation sign/magnitude via inline `rgba` (positive = warm, negative = cool); selected row highlighted:

```vue
<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="matrix.tools.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      MDC 설정 데이터가 없습니다.
    </div>
    <div
      v-else
      class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
      <table class="min-w-full text-left text-xs">
        <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
          <tr>
            <th class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
              EQP
            </th>
            <th
              v-for="cond in matrix.conditions"
              :key="cond"
              class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]"
            >
              {{ cond }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(tool, row) in matrix.tools"
            :key="tool"
            class="border-t border-(--sk-border-soft)"
            :class="row === 0 ? 'bg-(--sk-muted-surface)' : ''"
          >
            <td class="whitespace-nowrap px-3 py-2 font-mono font-bold text-(--sk-ink)">
              {{ tool }}
              <span
                v-if="row === 0"
                class="ml-1 rounded bg-(--sk-ink) px-1 text-[9px] text-white dark:text-zinc-900"
              >선택</span>
            </td>
            <td
              v-for="(cond, col) in matrix.conditions"
              :key="cond"
              class="whitespace-nowrap px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)"
              :style="cellStyle(row, col)"
            >
              {{ formatCell(matrix.values[row]?.[col]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { buildMdcMatrix, cellDeviation } from '~/utils/mdcMatrix'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  selectedEqp: string
}>()

const matrix = computed(() => buildMdcMatrix(props.settings, props.selectedEqp))

const formatCell = (v: number | null | undefined) =>
  v === null || v === undefined ? '-' : v.toFixed(4)

// Warm (rose) for above-baseline, cool (sky) for below; alpha = magnitude.
const cellStyle = (row: number, col: number) => {
  if (row === 0) return {}
  const dev = cellDeviation(matrix.value, row, col)
  if (dev === 0) return {}
  const alpha = Math.min(Math.abs(dev) * 0.6, 0.6).toFixed(3)
  const rgb = dev > 0 ? '244, 63, 94' : '56, 189, 248'
  return { backgroundColor: `rgba(${rgb}, ${alpha})` }
}
</script>
```

- [ ] **Step 7: Playwright verify.**

Navigate to `http://localhost:3000/ebeam/cd-sem/m16b/hardware`, click **MDC**, confirm rows = tools (selected first, badged), columns = beam_condition, colored deviation cells. Screenshot → `.playwright-mcp/screenshots/mdc-panel.png`.

- [ ] **Step 8: Commit the panel.**

```bash
git add front-dev-home/app/components/ebeam/hardware/MdcPanel.vue
git commit -m "feat(hardware): MDC skew-matrix panel"
```

---

## Task 6: ResoCenterPanel

**Files:**
- Create: `front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue`

**Interfaces:**
- Consumes: `docs: Record<string, unknown>[]` (reso_center docs); `useEchart`/`useEchartsTheme`.
- Produces: none (leaf panel).

Each doc has: `CenterX`, `CenterY`, `BestReso`, `ResoDelta`, `ResoIScenter`, `Resolution_Range` (`['-10','-5','0','5','10']`), `Resolution_Range_Raw`/`Resolution_Range_Smooth` (dict keyed by those offsets → 5 numbers each), `beam_condition`, `timestamp`. The focus-sweep curve for the selected measurement plots, per offset, the raw vs smooth value. Use the **first** number of each offset's array as the sweep value (the 5 inner numbers are repeated samples; the panel shows the representative leading value — keep it simple and faithful).

- [ ] **Step 1: Implement `ResoCenterPanel.vue`.**

Create the file (template first). Three ECharts blocks are simplest as one inline-option-per-`<div ref>`; to avoid three near-identical `useEchart` setups in one giant file, keep this panel to a single `<script setup>` with three chart refs (panel stays well under 900 lines):

```vue
<template>
  <div class="mt-3 space-y-3">
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-(--sk-ink-muted)">Beam Condition</span>
      <USelect
        v-model="beamCondition"
        :items="beamConditionItems"
        size="xs"
        icon="i-lucide-filter"
        class="w-48"
      />
      <span class="ml-auto" />
      <USelect
        v-model="selectedTs"
        :items="timestampItems"
        size="xs"
        icon="i-lucide-clock"
        placeholder="측정 시각 선택"
        class="w-56"
      />
    </div>

    <div class="grid gap-3 lg:grid-cols-2">
      <!-- Center-drift scatter (CenterX vs CenterY, latest emphasized) -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">Center Drift</div>
        <div
          ref="scatterEl"
          class="h-72 w-full"
        />
      </div>
      <!-- BestReso / ResoDelta trend (click → select) -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">BestReso · ResoDelta</div>
        <div
          ref="trendEl"
          class="h-72 w-full"
        />
      </div>
    </div>

    <!-- Focus-sweep curve for the selected measurement (Raw vs Smooth) -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">Focus Sweep (Raw vs Smooth)</div>
      <div
        ref="sweepEl"
        class="h-64 w-full"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{ docs: Record<string, unknown>[] }>()

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}
const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const beamConditions = computed(() =>
  Array.from(new Set(props.docs.map(d => String(d.beam_condition ?? '')).filter(Boolean))).sort()
)
const beamCondition = ref('all')
const beamConditionItems = computed(() => [
  { label: 'All conditions', value: 'all' },
  ...beamConditions.value.map(c => ({ label: c, value: c }))
])
const filtered = computed(() =>
  beamCondition.value === 'all'
    ? props.docs
    : props.docs.filter(d => String(d.beam_condition ?? '') === beamCondition.value)
)
const ordered = computed(() => [...filtered.value].sort((a, b) => tsOf(a).localeCompare(tsOf(b))))

const timestampItems = computed(() => [...ordered.value].map(tsOf).reverse())
const selectedTs = ref('')
watch(timestampItems, (items) => {
  if (!items.includes(selectedTs.value)) selectedTs.value = items[0] ?? ''
}, { immediate: true })
const selectedDoc = computed(() => ordered.value.find(d => tsOf(d) === selectedTs.value))

const scatterEl = ref<HTMLDivElement | null>(null)
const trendEl = ref<HTMLDivElement | null>(null)
const sweepEl = ref<HTMLDivElement | null>(null)

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const scatterOption = computed<EChartsOption>(() => {
  const pts = ordered.value.map(d => ({ ts: tsOf(d), x: num(d.CenterX), y: num(d.CenterY) }))
  const latest = pts[pts.length - 1]
  return {
    grid: { left: 48, right: 16, top: 16, bottom: 36 },
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.data[2]}<br/>X ${p.data[0]} · Y ${p.data[1]}` },
    xAxis: { type: 'value', name: 'CenterX', scale: true, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'CenterY', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'scatter', symbolSize: 7, itemStyle: { color: c0.value, opacity: 0.5 },
        data: pts.map(p => [p.x, p.y, p.ts])
      },
      ...(latest ? [{
        type: 'scatter' as const, symbolSize: 14,
        itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
        data: [[latest.x, latest.y, `${latest.ts} (latest)`]]
      }] : [])
    ]
  }
})

const trendOption = computed<EChartsOption>(() => {
  const rows = ordered.value
  return {
    grid: { left: 56, right: 56, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', name: 'BestReso', scale: true, axisLabel: { fontSize: 10 } },
      { type: 'value', name: 'ResoDelta', scale: true, axisLabel: { fontSize: 10 } }
    ],
    series: [
      {
        name: 'BestReso', type: 'line', yAxisIndex: 0,
        lineStyle: { color: c0.value }, itemStyle: { color: c0.value },
        data: rows.map(d => ({ name: tsOf(d), value: [toEpoch(tsOf(d)), num(d.BestReso)], symbolSize: tsOf(d) === selectedTs.value ? 12 : 5 }))
      },
      {
        name: 'ResoDelta', type: 'line', yAxisIndex: 1,
        lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value },
        data: rows.map(d => ({ name: tsOf(d), value: [toEpoch(tsOf(d)), num(d.ResoDelta)], symbolSize: tsOf(d) === selectedTs.value ? 11 : 4 }))
      }
    ]
  }
})

const sweepOption = computed<EChartsOption>(() => {
  const d = selectedDoc.value
  const offsets = Array.isArray(d?.Resolution_Range) ? (d!.Resolution_Range as unknown[]).map(String) : []
  const raw = (d?.Resolution_Range_Raw ?? {}) as Record<string, unknown>
  const smooth = (d?.Resolution_Range_Smooth ?? {}) as Record<string, unknown>
  const lead = (bag: Record<string, unknown>, off: string): number => {
    const a = bag[off]
    return Array.isArray(a) ? num(a[0]) : NaN
  }
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: offsets, name: 'offset', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: 'Raw', type: 'line', smooth: false, lineStyle: { color: c0.value }, itemStyle: { color: c0.value }, data: offsets.map(o => lead(raw, o)) },
      { name: 'Smooth', type: 'line', smooth: true, lineStyle: { color: c1.value }, itemStyle: { color: c1.value }, data: offsets.map(o => lead(smooth, o)) }
    ]
  }
})

useEchart(scatterEl, scatterOption)
useEchart(trendEl, trendOption, { onClick: ts => { selectedTs.value = ts } })
useEchart(sweepEl, sweepOption)
</script>
```

- [ ] **Step 2: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS for this file (remaining errors: FDC/SCE panels not yet created).

- [ ] **Step 3: Playwright verify.**

Navigate, click **Reso Center**, confirm scatter + dual-axis trend + focus-sweep curve, and that clicking a trend point + changing the timestamp updates the sweep. Screenshot → `.playwright-mcp/screenshots/reso-center-panel.png`.

- [ ] **Step 4: Commit.**

```bash
git add front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue
git commit -m "feat(hardware): Reso Center panel — drift scatter + trend + focus sweep"
```

---

## Task 7: `fdcValues` util (TDD) + FdcPanel

**Files:**
- Create: `front-dev-home/app/utils/fdcValues.ts`
- Test: `front-dev-home/app/utils/fdcValues.test.ts`
- Create: `front-dev-home/app/components/ebeam/hardware/FdcPanel.vue`

**Interfaces:**
- Consumes: nothing (pure) for util; `parseFdcValues`, the typed shapes, for the panel.
- Produces (used by `FdcPanel`):

```ts
export type FdcKey = 'TemperatureEchuck' | 'LaserPower' | 'SPMVoltages' | 'ContactpinConductionInfo'
export interface TemperatureValue { position: string; temp: number }
export interface LaserPowerValue { pairs: { x: number; y: number }[] }
export interface SpmVoltagesValue { channel: string; judgment: string; profile: number[] }
export interface ContactpinValue { channel: string; judgment: string; values: number[] }
export type FdcParsed =
  | { key: 'TemperatureEchuck'; data: TemperatureValue }
  | { key: 'LaserPower'; data: LaserPowerValue }
  | { key: 'SPMVoltages'; data: SpmVoltagesValue }
  | { key: 'ContactpinConductionInfo'; data: ContactpinValue }
  | { key: string; data: null }
export function parseFdcValues(values: unknown[]): FdcParsed
```

Layout rules from §6.3 (the leading element of `values` is the `fdc_key`; index 1 is the constant `'0'`):
- `TemperatureEchuck` → `[key, '0', position, temp]` → `{ position, temp }`.
- `LaserPower` → `[key, '0', x1, y1, x2, y2]` → `{ pairs: [{x:x1,y:y1},{x:x2,y:y2}] }`.
- `SPMVoltages` → `[key, '0', channel(A/B/C), n, n, n, judgment(spline|quartic), …~100 nums]` → `{ channel, judgment, profile: trailing numbers after the judgment }`. The judgment is the **first non-numeric string at/after index 3**; everything numeric after it is the profile.
- `ContactpinConductionInfo` → `[key, '0', channel, n, judgment(Conduction|NotConduction), …5 nums]` → `{ channel, judgment, values: the 5 trailing numbers }`. Judgment is the first non-numeric token at/after index 3.

- [ ] **Step 1: Write the failing test.**

Create `front-dev-home/app/utils/fdcValues.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseFdcValues } from './fdcValues.ts'

test('TemperatureEchuck → position + temp', () => {
  const p = parseFdcValues(['TemperatureEchuck', '0', '1', '23.39053'])
  assert.deepEqual(p, { key: 'TemperatureEchuck', data: { position: '1', temp: 23.39053 } })
})

test('LaserPower → two xy pairs', () => {
  const p = parseFdcValues(['LaserPower', '0', '0.78', '0.73', '341990938', '46504250'])
  assert.equal(p.key, 'LaserPower')
  assert.deepEqual((p.data as any).pairs, [{ x: 0.78, y: 0.73 }, { x: 341990938, y: 46504250 }])
})

test('SPMVoltages → channel, judgment, numeric profile after judgment', () => {
  const p = parseFdcValues(['SPMVoltages', '0', 'B', '7', '1', '1', 'spline', '-0.2', '0', '-0.4'])
  assert.equal(p.key, 'SPMVoltages')
  assert.equal((p.data as any).channel, 'B')
  assert.equal((p.data as any).judgment, 'spline')
  assert.deepEqual((p.data as any).profile, [-0.2, 0, -0.4])
})

test('ContactpinConductionInfo → channel, judgment, 5 values', () => {
  const p = parseFdcValues(['ContactpinConductionInfo', '0', 'A', '5', 'NotConduction', '-25.5', '-0.9', '24.6', '25.0', '182501'])
  assert.equal(p.key, 'ContactpinConductionInfo')
  assert.equal((p.data as any).channel, 'A')
  assert.equal((p.data as any).judgment, 'NotConduction')
  assert.deepEqual((p.data as any).values, [-25.5, -0.9, 24.6, 25.0, 182501])
})

test('unknown key → data null', () => {
  const p = parseFdcValues(['Mystery', '0', '1'])
  assert.deepEqual(p, { key: 'Mystery', data: null })
})
```

- [ ] **Step 2: Run to verify it fails.**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './fdcValues.ts'`.

- [ ] **Step 3: Implement `fdcValues.ts`.**

```ts
// Pure: parse one fdc doc's `values` list (which starts with the fdc_key)
// into a typed shape per §6.3. The judgment token is the first non-numeric
// string at/after index 3; numeric values after it form the profile.

export type FdcKey = 'TemperatureEchuck' | 'LaserPower' | 'SPMVoltages' | 'ContactpinConductionInfo'

export interface TemperatureValue { position: string; temp: number }
export interface LaserPowerValue { pairs: { x: number; y: number }[] }
export interface SpmVoltagesValue { channel: string; judgment: string; profile: number[] }
export interface ContactpinValue { channel: string; judgment: string; values: number[] }

export type FdcParsed =
  | { key: 'TemperatureEchuck'; data: TemperatureValue }
  | { key: 'LaserPower'; data: LaserPowerValue }
  | { key: 'SPMVoltages'; data: SpmVoltagesValue }
  | { key: 'ContactpinConductionInfo'; data: ContactpinValue }
  | { key: string; data: null }

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}
const isNumeric = (v: unknown): boolean => Number.isFinite(num(v))

// Index of the first non-numeric token at/after `from` (the judgment slot).
const judgmentIndex = (values: unknown[], from: number): number => {
  for (let i = from; i < values.length; i++) if (!isNumeric(values[i])) return i
  return -1
}

export const parseFdcValues = (values: unknown[]): FdcParsed => {
  const key = String(values[0] ?? '')

  if (key === 'TemperatureEchuck') {
    return { key, data: { position: String(values[2] ?? ''), temp: num(values[3]) } }
  }

  if (key === 'LaserPower') {
    return {
      key,
      data: {
        pairs: [
          { x: num(values[2]), y: num(values[3]) },
          { x: num(values[4]), y: num(values[5]) }
        ]
      }
    }
  }

  if (key === 'SPMVoltages') {
    const channel = String(values[2] ?? '')
    const ji = judgmentIndex(values, 3)
    const judgment = ji >= 0 ? String(values[ji]) : ''
    const profile = (ji >= 0 ? values.slice(ji + 1) : []).map(num).filter(Number.isFinite)
    return { key, data: { channel, judgment, profile } }
  }

  if (key === 'ContactpinConductionInfo') {
    const channel = String(values[2] ?? '')
    const ji = judgmentIndex(values, 3)
    const judgment = ji >= 0 ? String(values[ji]) : ''
    const vals = (ji >= 0 ? values.slice(ji + 1) : []).map(num).filter(Number.isFinite)
    return { key, data: { channel, judgment, values: vals } }
  }

  return { key, data: null }
}
```

- [ ] **Step 4: Run to verify pass.**

Run: `npm --prefix front-dev-home test`
Expected: PASS.

- [ ] **Step 5: Commit the util.**

```bash
git add front-dev-home/app/utils/fdcValues.ts front-dev-home/app/utils/fdcValues.test.ts
git commit -m "feat(hardware): fdcValues util — typed parse per fdc_key (TDD)"
```

- [ ] **Step 6: Implement `FdcPanel.vue`.**

Create `front-dev-home/app/components/ebeam/hardware/FdcPanel.vue` (template first). Group docs by `fdc_key`, render a sub-tab row, and switch the body per key. Use one chart `ref` for the temperature/laser/spm views and a plain table for contactpin. To keep the file focused, the chart option is computed from the active sub-tab's parsed docs:

```vue
<template>
  <div class="mt-3 space-y-3">
    <!-- fdc_key sub-tabs -->
    <div class="flex overflow-hidden rounded-[10px] border border-(--sk-border) w-fit">
      <button
        v-for="key in availableKeys"
        :key="key"
        type="button"
        class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
        :class="key === activeKey
          ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
          : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
        @click="activeKey = key"
      >
        {{ key }}
        <span class="ml-1 font-mono text-[10px] opacity-70">{{ grouped[key]?.length ?? 0 }}</span>
      </button>
    </div>

    <div
      v-if="availableKeys.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      FDC 데이터가 없습니다.
    </div>

    <!-- ContactpinConductionInfo → status table -->
    <div
      v-else-if="activeKey === 'ContactpinConductionInfo'"
      class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
      <table class="min-w-full text-left text-xs">
        <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
          <tr>
            <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">Timestamp</th>
            <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">Ch</th>
            <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">Judgment</th>
            <th class="px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]">Values</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in contactpinRows"
            :key="i"
            class="border-t border-(--sk-border-soft)"
          >
            <td class="px-3 py-2 font-mono text-(--sk-ink)">{{ row.ts }}</td>
            <td class="px-3 py-2 font-mono text-(--sk-ink)">{{ row.channel }}</td>
            <td class="px-3 py-2">
              <span
                class="rounded px-1.5 py-0.5 text-[10px] font-bold"
                :class="row.judgment === 'Conduction'
                  ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
                  : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
              >{{ row.judgment }}</span>
            </td>
            <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)">
              {{ row.values.join(' · ') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SPMVoltages → profile per A/B/C + judgment badge, timestamp-selectable -->
    <div
      v-else-if="activeKey === 'SPMVoltages'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="flex items-center gap-2">
          <span
            v-for="b in spmJudgments"
            :key="b.channel"
            class="rounded bg-(--sk-muted-surface) px-1.5 py-0.5 font-mono text-[10px] font-bold text-(--sk-ink)"
          >{{ b.channel }}: {{ b.judgment }}</span>
        </div>
        <USelect
          v-model="spmTs"
          :items="spmTimestampItems"
          size="xs"
          icon="i-lucide-clock"
          class="w-56"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </div>

    <!-- TemperatureEchuck / LaserPower → trend chart -->
    <div
      v-else
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">{{ activeKey }} trend</div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { parseFdcValues } from '~/utils/fdcValues'

const props = defineProps<{ docs: Record<string, unknown>[] }>()

const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')
const valuesOf = (d: Record<string, unknown>) => (Array.isArray(d.values) ? d.values : [])

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')
const c2 = computed(() => palette.value[2] ?? '#7B6CC4')

const grouped = computed(() => {
  const g: Record<string, Record<string, unknown>[]> = {}
  for (const d of props.docs) {
    const key = String(d.fdc_key ?? '')
    if (!key) continue
    ;(g[key] ??= []).push(d)
  }
  for (const k of Object.keys(g)) g[k]!.sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
  return g
})
const availableKeys = computed(() => Object.keys(grouped.value).sort())
const activeKey = ref('')
watch(availableKeys, (keys) => {
  if (!keys.includes(activeKey.value)) activeKey.value = keys[0] ?? ''
}, { immediate: true })

const activeDocs = computed(() => grouped.value[activeKey.value] ?? [])
const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const chartEl = ref<HTMLDivElement | null>(null)

// --- ContactpinConductionInfo ---
const contactpinRows = computed(() =>
  activeDocs.value.map((d) => {
    const p = parseFdcValues(valuesOf(d))
    const data = p.key === 'ContactpinConductionInfo' ? p.data : null
    return { ts: tsOf(d), channel: data?.channel ?? '', judgment: data?.judgment ?? '', values: data?.values ?? [] }
  })
)

// --- SPMVoltages ---
const spmTimestampItems = computed(() =>
  Array.from(new Set(activeDocs.value.map(tsOf))).reverse()
)
const spmTs = ref('')
watch(spmTimestampItems, (items) => {
  if (!items.includes(spmTs.value)) spmTs.value = items[0] ?? ''
}, { immediate: true })
const spmAtTs = computed(() =>
  activeDocs.value
    .filter(d => tsOf(d) === spmTs.value)
    .map(d => parseFdcValues(valuesOf(d)))
    .filter(p => p.key === 'SPMVoltages')
)
const spmJudgments = computed(() =>
  spmAtTs.value.map(p => ({ channel: (p.data as any).channel as string, judgment: (p.data as any).judgment as string }))
)

const chartOption = computed<EChartsOption>(() => {
  if (activeKey.value === 'SPMVoltages') {
    const colors = [c0.value, c1.value, c2.value]
    return {
      grid: { left: 48, right: 16, top: 24, bottom: 36 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'category', name: 'index', axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
      series: spmAtTs.value.map((p, i) => ({
        name: (p.data as any).channel as string,
        type: 'line', smooth: true, showSymbol: false,
        lineStyle: { color: colors[i % colors.length] },
        itemStyle: { color: colors[i % colors.length] },
        data: (p.data as any).profile as number[]
      }))
    }
  }

  if (activeKey.value === 'LaserPower') {
    const pts = activeDocs.value.map(d => ({ ts: tsOf(d), parsed: parseFdcValues(valuesOf(d)) }))
    const pair = (i: number) => pts.map(p => ({
      name: p.ts,
      value: [toEpoch(p.ts), ((p.parsed.data as any)?.pairs?.[i]?.x ?? NaN)]
    }))
    return {
      grid: { left: 56, right: 56, top: 24, bottom: 36 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
      yAxis: [
        { type: 'value', name: 'pair 1', scale: true, axisLabel: { fontSize: 10 } },
        { type: 'value', name: 'pair 2', scale: true, axisLabel: { fontSize: 10 } }
      ],
      series: [
        { name: 'pair 1 (x)', type: 'line', yAxisIndex: 0, lineStyle: { color: c0.value }, itemStyle: { color: c0.value }, data: pair(0) },
        { name: 'pair 2 (x)', type: 'line', yAxisIndex: 1, lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value }, data: pair(1) }
      ]
    }
  }

  // TemperatureEchuck → one line per position (1/2/3)
  const byPos: Record<string, { ts: string; temp: number }[]> = {}
  for (const d of activeDocs.value) {
    const p = parseFdcValues(valuesOf(d))
    if (p.key !== 'TemperatureEchuck') continue
    const pos = (p.data as any).position as string
    ;(byPos[pos] ??= []).push({ ts: tsOf(d), temp: (p.data as any).temp as number })
  }
  const colors = [c0.value, c1.value, c2.value]
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '°C', scale: true, axisLabel: { fontSize: 10 } },
    series: Object.keys(byPos).sort().map((pos, i) => ({
      name: `pos ${pos}`, type: 'line', showSymbol: true,
      lineStyle: { color: colors[i % colors.length] }, itemStyle: { color: colors[i % colors.length] },
      data: byPos[pos]!.map(r => ({ name: r.ts, value: [toEpoch(r.ts), r.temp] }))
    }))
  }
})

useEchart(chartEl, chartOption)
</script>
```

- [ ] **Step 7: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS for this file (only SCE panel remains).

- [ ] **Step 8: Playwright verify.**

Navigate, click **FDC**, click through each fdc_key sub-tab (Temperature trend, LaserPower dual-axis, SPMVoltages profile + judgment badges, Contactpin status table). Screenshot each → `.playwright-mcp/screenshots/fdc-panel-<key>.png`.

- [ ] **Step 9: Commit the panel.**

```bash
git add front-dev-home/app/components/ebeam/hardware/FdcPanel.vue
git commit -m "feat(hardware): FDC panel — fdc_key sub-tabs (temp/laser/spm/contactpin)"
```

---

## Task 8: `sceCompare` util (TDD) + ScePanel

**Files:**
- Create: `front-dev-home/app/utils/sceCompare.ts`
- Test: `front-dev-home/app/utils/sceCompare.test.ts`
- Create: `front-dev-home/app/components/ebeam/hardware/ScePanel.vue`

**Interfaces:**
- Consumes: nothing (pure) for util; `flattenSettings`, `compareSettings`, `coefficientSeries` for the panel.
- Produces (used by `ScePanel`):

```ts
// Flatten SemCond/ImgCond/SCEParam (NOT Coefficients) into dotted leaf paths.
export function flattenSettings(node: Record<string, unknown>): Record<string, string>
export interface SceCompareRow {
  path: string
  selected: string
  siblings: Record<string, string>   // eqp_id → value
  differs: boolean                    // any sibling != selected
}
export function compareSettings(
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): SceCompareRow[]
// Two series (values[0], values[1]) indexed 0..359 for one eqp.
export function coefficientSeries(
  eqpSettings: Record<string, unknown> | undefined
): { v0: number[]; v1: number[] }
```

Rules:
- `flattenSettings` walks `SemCond`, `ImgCond`, `SCEParam` only (skip `Coefficients` and `FileInfo`). Array leaves join with `,`. Produces keys like `SemCond.SemCond_Vacc`, `ImgCond.ImgCond_Mag`.
- `compareSettings` builds the union of leaf paths across the selected eqp + siblings; `differs` true when any sibling's value differs from the selected eqp's value (missing counts as differing).
- `coefficientSeries` maps `Coefficients` (array of `{index, values:[a,b]}`) into two dense length-360 arrays by `index` (gaps → `NaN`).

- [ ] **Step 1: Write the failing test.**

Create `front-dev-home/app/utils/sceCompare.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { flattenSettings, compareSettings, coefficientSeries } from './sceCompare.ts'

const eqpA = {
  SemCond: { SemCond_Vacc: '800', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  Coefficients: [{ index: 0, values: [0.00884, 0.964293] }, { index: 2, values: [0.01, 0.97] }]
}
const eqpB = {
  SemCond: { SemCond_Vacc: '500', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  Coefficients: []
}

test('flattenSettings: dotted leaf paths, arrays joined, Coefficients skipped', () => {
  const flat = flattenSettings(eqpA)
  assert.equal(flat['SemCond.SemCond_Vacc'], '800')
  assert.equal(flat['ImgCond.ImgCond_Mag'], '150003298,150003298')
  assert.ok(!Object.keys(flat).some(k => k.startsWith('Coefficients')))
})

test('compareSettings: flags only the differing Vacc row', () => {
  const rows = compareSettings({ A: eqpA, B: eqpB }, 'A')
  const vacc = rows.find(r => r.path === 'SemCond.SemCond_Vacc')!
  assert.equal(vacc.selected, '800')
  assert.equal(vacc.siblings['B'], '500')
  assert.equal(vacc.differs, true)

  const ip = rows.find(r => r.path === 'SemCond.SemCond_Ip')!
  assert.equal(ip.differs, false)
})

test('coefficientSeries: dense 360-length arrays, gaps NaN', () => {
  const { v0, v1 } = coefficientSeries(eqpA)
  assert.equal(v0.length, 360)
  assert.equal(v0[0], 0.00884)
  assert.equal(v1[2], 0.97)
  assert.ok(Number.isNaN(v0[1]))
})

test('coefficientSeries: undefined eqp → all-NaN 360 arrays', () => {
  const { v0 } = coefficientSeries(undefined)
  assert.equal(v0.length, 360)
  assert.ok(v0.every(Number.isNaN))
})
```

- [ ] **Step 2: Run to verify it fails.**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './sceCompare.ts'`.

- [ ] **Step 3: Implement `sceCompare.ts`.**

```ts
// Pure: SCE settings comparison (selected eqp vs in-fab siblings) + the
// Coefficients[0..359] curve series. §7.5.

const SECTIONS = ['SemCond', 'ImgCond', 'SCEParam'] as const

const leafValue = (v: unknown): string => {
  if (Array.isArray(v)) return v.map(String).join(',')
  if (v === null || v === undefined) return ''
  return String(v)
}

export const flattenSettings = (node: Record<string, unknown>): Record<string, string> => {
  const out: Record<string, string> = {}
  for (const section of SECTIONS) {
    const sub = node[section]
    if (!sub || typeof sub !== 'object' || Array.isArray(sub)) continue
    for (const [k, v] of Object.entries(sub as Record<string, unknown>)) {
      out[`${section}.${k}`] = leafValue(v)
    }
  }
  return out
}

export interface SceCompareRow {
  path: string
  selected: string
  siblings: Record<string, string>
  differs: boolean
}

export const compareSettings = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string
): SceCompareRow[] => {
  const selectedFlat = flattenSettings(settings[selectedEqp] ?? {})
  const siblingIds = Object.keys(settings).filter(id => id !== selectedEqp).sort()
  const siblingFlats = siblingIds.map(id => [id, flattenSettings(settings[id] ?? {})] as const)

  const paths = new Set<string>(Object.keys(selectedFlat))
  for (const [, flat] of siblingFlats) for (const p of Object.keys(flat)) paths.add(p)

  return [...paths].sort().map((path): SceCompareRow => {
    const selected = selectedFlat[path] ?? ''
    const siblings: Record<string, string> = {}
    let differs = false
    for (const [id, flat] of siblingFlats) {
      const val = flat[path] ?? ''
      siblings[id] = val
      if (val !== selected) differs = true
    }
    return { path, selected, siblings, differs }
  })
}

export const coefficientSeries = (
  eqpSettings: Record<string, unknown> | undefined
): { v0: number[]; v1: number[] } => {
  const v0 = Array.from({ length: 360 }, () => NaN)
  const v1 = Array.from({ length: 360 }, () => NaN)
  const coeffs = eqpSettings?.Coefficients
  if (Array.isArray(coeffs)) {
    for (const c of coeffs) {
      const idx = Number((c as Record<string, unknown>)?.index)
      const vals = (c as Record<string, unknown>)?.values
      if (!Number.isInteger(idx) || idx < 0 || idx > 359 || !Array.isArray(vals)) continue
      v0[idx] = Number(vals[0])
      v1[idx] = Number(vals[1])
    }
  }
  return { v0, v1 }
}
```

- [ ] **Step 4: Run to verify pass.**

Run: `npm --prefix front-dev-home test`
Expected: PASS.

- [ ] **Step 5: Commit the util.**

```bash
git add front-dev-home/app/utils/sceCompare.ts front-dev-home/app/utils/sceCompare.test.ts
git commit -m "feat(hardware): sceCompare util — settings diff + coefficient series (TDD)"
```

- [ ] **Step 6: Implement `ScePanel.vue`.**

Create `front-dev-home/app/components/ebeam/hardware/ScePanel.vue` (template first):

```vue
<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="!hasSelected"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      SCE 설정 데이터가 없습니다.
    </div>

    <template v-else>
      <!-- Settings compare table: selected vs siblings, diffs flagged -->
      <div class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">Setting</th>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">{{ selectedEqp }} (선택)</th>
              <th
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]"
              >
                {{ id }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.path"
              class="border-t border-(--sk-border-soft)"
              :class="row.differs ? 'bg-amber-50 dark:bg-amber-950/30' : ''"
            >
              <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">{{ row.path }}</td>
              <td class="px-3 py-2 font-mono font-bold text-(--sk-ink)">{{ row.selected || '-' }}</td>
              <td
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono"
                :class="row.siblings[id] !== row.selected ? 'text-(--sk-bad) font-bold' : 'text-(--sk-ink)'"
              >
                {{ row.siblings[id] || '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Coefficients[0..359] overlay: values[0] / values[1], selected vs one sibling -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <div class="text-xs font-bold text-(--sk-ink)">Coefficients (0–359)</div>
          <USelect
            v-model="overlayEqp"
            :items="overlayItems"
            size="xs"
            class="w-44"
          />
        </div>
        <div
          ref="chartEl"
          class="h-80 w-full"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { compareSettings, coefficientSeries } from '~/utils/sceCompare'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  selectedEqp: string
}>()

const hasSelected = computed(() => Boolean(props.settings[props.selectedEqp]))
const siblingIds = computed(() => Object.keys(props.settings).filter(id => id !== props.selectedEqp).sort())
const rows = computed(() => compareSettings(props.settings, props.selectedEqp))

const overlayItems = computed(() => [
  { label: 'overlay 없음', value: 'none' },
  ...siblingIds.value.map(id => ({ label: id, value: id }))
])
const overlayEqp = ref('none')

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')
const c2 = computed(() => palette.value[2] ?? '#7B6CC4')
const c3 = computed(() => palette.value[3] ?? '#B0843C')

const chartEl = ref<HTMLDivElement | null>(null)
const indices = Array.from({ length: 360 }, (_, i) => i)

const chartOption = computed<EChartsOption>(() => {
  const sel = coefficientSeries(props.settings[props.selectedEqp])
  const sib = overlayEqp.value !== 'none' ? coefficientSeries(props.settings[overlayEqp.value]) : null
  const line = (name: string, data: number[], color: string, dashed = false) => ({
    name, type: 'line' as const, showSymbol: false, smooth: false,
    lineStyle: { color, width: 1.2, type: dashed ? ('dashed' as const) : ('solid' as const) },
    itemStyle: { color }, data
  })
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: indices, name: 'index', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      line(`${props.selectedEqp} v0`, sel.v0, c0.value),
      line(`${props.selectedEqp} v1`, sel.v1, c1.value),
      ...(sib ? [line(`${overlayEqp.value} v0`, sib.v0, c2.value, true), line(`${overlayEqp.value} v1`, sib.v1, c3.value, true)] : [])
    ]
  }
})

useEchart(chartEl, chartOption)
</script>
```

- [ ] **Step 7: Typecheck.**

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS for the whole app now (all panels exist).

- [ ] **Step 8: Playwright verify.**

Navigate, click **SCE**, confirm the settings-compare table (diff rows highlighted, differing sibling cells in bad-tone) and the Coefficients curve; pick a sibling in the overlay dropdown → two extra dashed series appear. Screenshot → `.playwright-mcp/screenshots/sce-panel.png`.

- [ ] **Step 9: Commit the panel.**

```bash
git add front-dev-home/app/components/ebeam/hardware/ScePanel.vue
git commit -m "feat(hardware): SCE panel — settings compare + coefficient overlay"
```

---

## Task 9: Final wiring + deep-link + full-page Playwright pass

**Files:**
- (No new files) — verification + any fix-ups to `HardwareView.vue` discovered here.

- [ ] **Step 1: Run the full test + typecheck gate.**

Run: `npm --prefix front-dev-home test`
Expected: PASS for `beamMetrics`, `mdcMatrix`, `fdcValues`, `sceCompare` (plus pre-existing `skewGrouping`/`pmPlanning`).

Run: `npm --prefix front-dev-home run typecheck`
Expected: PASS (no hardware errors).

Run: `npm --prefix front-dev-home run lint`
Expected: PASS (fix any lint nits in the new files).

- [ ] **Step 2: Deep-link smoke via Playwright.**

Navigate to a deep link with explicit params, e.g.:
`http://localhost:3000/ebeam/cd-sem/m16b/hardware?eqp_id=<a-real-eqp-from-the-list>&start=2026-04-01T00:00:00Z&end=2026-05-24T09:00:00Z`

Confirm:
1. The list rail pre-selects the `eqp_id` from the query (highlighted row).
2. The page lands on the **default panel** (BM/PM — no `service` param this round).
3. Switching to BSM/Reso/FDC shows data scoped to the windowed range.

Screenshot → `.playwright-mcp/screenshots/hardware-deeplink.png`.

- [ ] **Step 3: Full panel sweep.**

For a tool with data, click through **BM/PM → BSM → Reso Center → FDC → MDC → SCE** in one session, confirming each renders without console errors (`browser_console_messages`). Screenshot the final state → `.playwright-mcp/screenshots/hardware-all-panels.png`.

- [ ] **Step 4: Commit any fix-ups.**

```bash
git add -A
git commit -m "chore(hardware): final wiring + deep-link verification fix-ups"
```

(If no fix-ups were needed, skip the commit.)

---

## Self-Review

**Spec §7 panel coverage:**

| Spec §7 panel | Task |
| --- | --- |
| §7.1 BSM beam explorer (beam_condition filter, two scalar trends, two metric radars, scalar header cards, CSV; data-driven selectors + auto radial range) | Task 3 (`beamMetrics`) + Task 4 (rebuild) |
| §7.2 Reso Center (drift scatter, BestReso/ResoDelta trend, focus-sweep Raw/Smooth) | Task 6 |
| §7.3 FDC fdc_key sub-tabs (Temperature 3-pos, LaserPower dual-axis, SPMVoltages profile + judgment, Contactpin status table) | Task 7 (`fdcValues` + panel) |
| §7.4 MDC skew matrix (rows×beam_condition, deviation-from-selected color) | Task 5 (`mdcMatrix` + panel) |
| §7.5 SCE settings-compare table + Coefficients[0..359] overlay | Task 8 (`sceCompare` + panel) |

**Spec §10 frontend-change coverage:**

| §10 change | Task |
| --- | --- |
| `useHardwareApi.ts`: add `reso-center | mdc | sce` to `HardwareServiceKey` | Task 1 |
| build `/${slug}/hardware/${eqpId}/${service}` (eqp as segment) | Task 1 |
| `fabId` → `fabName` (query key `fab_name`) | Task 1 + Task 2 (call site) |
| add `start`/`end` | Task 1 + Task 2 |
| add `docs`/`settings` to payload | Task 1 |
| drop `BsmBlock`/`BsmSummaryRow`/`BsmProfile` | Task 1 |
| `HardwareView.vue`: call site `fabId:` → `fabName:` | Task 2 |
| `HardwareView.vue`: read deep-link query (`eqp_id`/`start`/`end`) → pre-select tool + set window | Task 2 + Task 9 |
| BSM components reworked to data-driven explorer | Task 4 |
| new panels for `reso-center`/`fdc`/`mdc`/`sce` | Tasks 5–8 |

**Spec §4 deep-link contract:** page route `/ebeam/cd-sem/<fab>/hardware?eqp_id=&start=&end=`, pre-select tool, set window, land on default panel (no `service`) — Task 2 (implementation) + Task 9 (verification).

**Type consistency:** `HardwareServiceKey` (Task 1) is consumed unchanged by Task 2's tabs and panel routing. Panel prop contracts declared in Task 2's `<EbeamHardware*>` mounts match each panel's `defineProps` (Tasks 4–8): `docs: Record<string, unknown>[]` (BSM/Reso/FDC), `settings: Record<string, Record<string, unknown>>` + `selectedEqp: string` (MDC/SCE), BSM additionally `fetchedAt: string`. The trend-chart child contract (`points: {ts,value}[]`, `selected`, `@select`) declared in Task 4 is used only inside `BsmPanel`. Util return types (`BeamMetricOption`, `MdcMatrix`, `FdcParsed`, `SceCompareRow`) are defined in their util tasks and imported by exactly one panel each.

**Placeholder scan:** no TBD/TODO; every code step shows complete code; every test step shows the actual `node:test` body; every component step shows the full `<template>` + `<script setup>`.
