# AFM Export Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user export an AFM measurement's data as CSV (per-dataset and combined), download the selected point's profile SVG, and get meaningful filenames on the existing chart PNG downloads — all from the detail page `pages/afm/[tool]/[filename].vue`.

**Architecture:** Reuse skewnono's existing `utils/csvDownload.ts` (UTF-8-BOM/CRLF Excel fix) and `useEchart`'s already-mounted hover PNG button rather than porting the legacy project's export code. Add a pure CSV-builder util (`utils/afmExport.ts`, unit-tested with `node --test`), split a `downloadCsvRaw` primitive out of `downloadCsv`, and wire a `UDropdownMenu` export menu into the detail page. Chart PNG export becomes a one-line `exportName` pass-through per chart.

**Tech Stack:** Nuxt 4, NuxtUI v4.6.1 (`UDropdownMenu`), TypeScript, ECharts (via `composables/useEchart.ts`), Node's built-in test runner (`node --test`, type-stripping on Node v24).

## Global Constraints

- Frontend root for all paths below: `front-dev-home/`. Run all `npm` commands from there.
- Test runner is `node --test`; test files are colocated `app/**/*.test.ts`. Run one file with `node --test app/utils/<name>.test.ts`. Only **pure** functions are unit-tested — no DOM/Nuxt runtime in test imports (type-only imports from `~/composables/*` are erased by type-stripping and are safe).
- Import runtime values from utils by **relative path with `.ts` extension** inside test/util files (matches `app/utils/chartRange.test.ts`); rely on Nuxt **auto-import** for utils/composables inside `.vue` files (no explicit import line), and use explicit `import type` for types.
- CSV encoding lives in ONE place (`downloadCsvRaw`): UTF-8 BOM (`﻿`, U+FEFF) prefix, `\r\n` line endings. Do not re-implement BOM/blob logic elsewhere.
- Every commit message ends with the standard trailer:

  ```text
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NHWMRqfxSYaLcagApFG1tB
  ```

- Work on `main` (project convention); no feature branch.

---

### Task 1: Split `downloadCsvRaw` / `buildCsvContent` out of `downloadCsv`

**Files:**
- Modify: `front-dev-home/app/utils/csvDownload.ts`
- Test: `front-dev-home/app/utils/csvDownload.test.ts` (create)

**Interfaces:**
- Produces:
  - `buildCsvContent(headers: string[], rows: unknown[][]): string` — CRLF-joined, every cell quoted via `escapeCsvValue`, **no BOM**.
  - `downloadCsvRaw(filename: string, content: string): void` — prepends BOM, blobs, downloads; client-only; no-op on empty content.
  - `downloadCsv(filename: string, headers: string[], rows: unknown[][]): void` — unchanged public behaviour; now delegates.
  - `escapeCsvValue` (already exported) — unchanged.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/csvDownload.test.ts`:

```ts
// Pure-logic tests for csvDownload. Run: node --test app/utils/csvDownload.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCsvContent, escapeCsvValue } from './csvDownload.ts'

test('buildCsvContent joins header and rows with CRLF and quotes every value', () => {
  const out = buildCsvContent(['a', 'b'], [[1, 'x'], [2, 'y']])
  assert.equal(out, '"a","b"\r\n"1","x"\r\n"2","y"')
})

test('buildCsvContent escapes embedded quotes and keeps commas inside quotes', () => {
  const out = buildCsvContent(['h'], [['a"b'], ['c,d']])
  assert.equal(out, '"h"\r\n"a""b"\r\n"c,d"')
})

test('escapeCsvValue renders null/undefined as an empty quoted string', () => {
  assert.equal(escapeCsvValue(null), '""')
  assert.equal(escapeCsvValue(undefined), '""')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/csvDownload.test.ts`
Expected: FAIL — `buildCsvContent` is not exported (`SyntaxError`/`undefined is not a function`).

- [ ] **Step 3: Refactor `csvDownload.ts`**

Replace the current `downloadCsv` definition (lines 9-27) with the three functions below. Keep `escapeCsvValue` (lines 1-4) and everything after (`copyTextToClipboard`, `copyTableToClipboard`) untouched.

```ts
// Compose CSV text (no BOM): header + rows, every value escaped, CRLF-joined.
// Pure — safe to import and call under `node --test`.
export const buildCsvContent = (headers: string[], rows: unknown[][]): string => {
  const headerRow = headers.map(escapeCsvValue).join(',')
  const bodyRows = rows.map(row => row.map(escapeCsvValue).join(','))
  return [headerRow, ...bodyRows].join('\r\n')
}

// Download an arbitrary CSV string. Excel reads UTF-8 only when a BOM (U+FEFF)
// is present, so this is the single place the BOM is added. Client-only.
export const downloadCsvRaw = (filename: string, content: string): void => {
  if (!import.meta.client || content.length === 0) return

  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const downloadCsv = (
  filename: string,
  headers: string[],
  rows: unknown[][]
): void => {
  if (rows.length === 0) return
  downloadCsvRaw(filename, buildCsvContent(headers, rows))
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/csvDownload.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors in `utils/csvDownload.ts`.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/utils/csvDownload.ts app/utils/csvDownload.test.ts
git commit  # message below (append the standard trailer)
```

Message: `refactor(csv): extract downloadCsvRaw/buildCsvContent from downloadCsv`

---

### Task 2: AFM CSV builders (`utils/afmExport.ts`)

**Files:**
- Create: `front-dev-home/app/utils/afmExport.ts`
- Test: `front-dev-home/app/utils/afmExport.test.ts`

**Interfaces:**
- Consumes: `buildCsvContent` from `./csvDownload.ts` (Task 1); types `AfmInformation`, `AfmSummaryRow`, `AfmDetailRow`, `AfmProfilePoint` from `~/composables/useAfmDetailApi` (type-only).
- Produces:
  - `interface CsvTable { headers: string[]; rows: unknown[][] }`
  - `buildInfoCsv(info: AfmInformation): CsvTable`
  - `buildSummaryCsv(summary: AfmSummaryRow[]): CsvTable`
  - `buildDetailedCsv(data: AfmDetailRow[]): CsvTable`
  - `buildProfileCsv(points: AfmProfilePoint[]): CsvTable`
  - `interface CsvSection { label: string; table: CsvTable }`
  - `buildCombinedContent(sections: CsvSection[]): string`

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/afmExport.test.ts`:

```ts
// Pure-logic tests for afmExport. Run: node --test app/utils/afmExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildInfoCsv,
  buildSummaryCsv,
  buildDetailedCsv,
  buildProfileCsv,
  buildCombinedContent
} from './afmExport.ts'

test('buildInfoCsv → key,value rows preserving null', () => {
  const t = buildInfoCsv({ 'Recipe ID': 'ABC', 'Lot ID': 'TT01', Missing: null })
  assert.deepEqual(t.headers, ['key', 'value'])
  assert.deepEqual(t.rows, [['Recipe ID', 'ABC'], ['Lot ID', 'TT01'], ['Missing', null]])
})

test('buildSummaryCsv collects dynamic measurement columns after Site/ITEM', () => {
  const t = buildSummaryCsv([
    { Site: '1', ITEM: 'MEAN', 'CD (nm)': 12, 'H (nm)': 3 },
    { Site: '1', ITEM: 'STDEV', 'CD (nm)': 0.5, 'H (nm)': 0.1 }
  ])
  assert.deepEqual(t.headers, ['Site', 'ITEM', 'CD (nm)', 'H (nm)'])
  assert.deepEqual(t.rows[0], ['1', 'MEAN', 12, 3])
})

test('buildSummaryCsv on empty input → headers only, no rows', () => {
  const t = buildSummaryCsv([])
  assert.deepEqual(t.headers, ['Site', 'ITEM'])
  assert.deepEqual(t.rows, [])
})

test('buildDetailedCsv unions keys across ragged rows, missing → empty', () => {
  const t = buildDetailedCsv([
    { 'Site ID': 'A', 'X (um)': 1 },
    { 'Site ID': 'B', 'X (um)': 2, Extra: 9 }
  ])
  assert.deepEqual(t.headers, ['Site ID', 'X (um)', 'Extra'])
  assert.deepEqual(t.rows[0], ['A', 1, ''])
  assert.deepEqual(t.rows[1], ['B', 2, 9])
})

test('buildProfileCsv → x,y,z', () => {
  const t = buildProfileCsv([{ x: 1, y: 2, z: 3 }])
  assert.deepEqual(t.headers, ['x', 'y', 'z'])
  assert.deepEqual(t.rows, [[1, 2, 3]])
})

test('buildCombinedContent labels sections and marks empty ones (no data)', () => {
  const out = buildCombinedContent([
    { label: 'Measurement Info', table: buildInfoCsv({ A: '1' }) },
    { label: 'Profile (selected point)', table: buildProfileCsv([]) }
  ])
  assert.equal(
    out,
    '## Measurement Info\r\n"key","value"\r\n"A","1"\r\n\r\n## Profile (selected point) (no data)'
  )
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/afmExport.test.ts`
Expected: FAIL — `Cannot find module './afmExport.ts'`.

- [ ] **Step 3: Write `afmExport.ts`**

Create `front-dev-home/app/utils/afmExport.ts`:

```ts
// Pure CSV builders for the AFM measurement-detail export menu. No DOM/Nuxt
// runtime imports so they run under `node --test`; the page wires these into
// downloadCsv / downloadCsvRaw from utils/csvDownload.
import { buildCsvContent } from './csvDownload.ts'
import type {
  AfmInformation,
  AfmSummaryRow,
  AfmDetailRow,
  AfmProfilePoint
} from '~/composables/useAfmDetailApi'

export interface CsvTable {
  headers: string[]
  rows: unknown[][]
}

// Column order = the given leading columns, then every other key in the order
// it first appears across rows. Ragged rows never drop a column.
const collectColumns = (
  rows: Record<string, unknown>[],
  leading: string[]
): string[] => {
  const seen = new Set(leading)
  const cols = [...leading]
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!seen.has(key)) {
        seen.add(key)
        cols.push(key)
      }
    }
  }
  return cols
}

const tableFromRows = (
  rows: Record<string, unknown>[],
  leading: string[]
): CsvTable => {
  const headers = collectColumns(rows, leading)
  const body = rows.map(row => headers.map(col => row[col] ?? ''))
  return { headers, rows: body }
}

export const buildInfoCsv = (info: AfmInformation): CsvTable => ({
  headers: ['key', 'value'],
  rows: Object.entries(info).map(([k, v]) => [k, v])
})

export const buildSummaryCsv = (summary: AfmSummaryRow[]): CsvTable => {
  if (summary.length === 0) return { headers: ['Site', 'ITEM'], rows: [] }
  return tableFromRows(summary as unknown as Record<string, unknown>[], ['Site', 'ITEM'])
}

export const buildDetailedCsv = (data: AfmDetailRow[]): CsvTable => {
  if (data.length === 0) return { headers: [], rows: [] }
  return tableFromRows(data as unknown as Record<string, unknown>[], [])
}

export const buildProfileCsv = (points: AfmProfilePoint[]): CsvTable => ({
  headers: ['x', 'y', 'z'],
  rows: points.map(p => [p.x, p.y, p.z])
})

export interface CsvSection {
  label: string
  table: CsvTable
}

// Stack labelled sections into one CSV string. Each section is prefixed with a
// '## <label>' line; empty tables render '## <label> (no data)' with no rows.
// Sections separated by a blank line. No BOM (downloadCsvRaw adds it).
export const buildCombinedContent = (sections: CsvSection[]): string =>
  sections
    .map(({ label, table }) =>
      table.rows.length === 0
        ? `## ${label} (no data)`
        : `## ${label}\r\n${buildCsvContent(table.headers, table.rows)}`
    )
    .join('\r\n\r\n')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/afmExport.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/utils/afmExport.ts app/utils/afmExport.test.ts
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add pure CSV builders for measurement export`

---

### Task 3: Export menu on the detail page

**Files:**
- Modify: `front-dev-home/app/pages/afm/[tool]/[filename].vue`

**Interfaces:**
- Consumes: `buildInfoCsv`, `buildSummaryCsv`, `buildDetailedCsv`, `buildProfileCsv`, `buildCombinedContent`, `CsvTable` (Task 2, auto-imported; `CsvTable` via `import type`); `downloadCsv`, `downloadCsvRaw` (Task 1, auto-imported); `DropdownMenuItem` from `@nuxt/ui`.
- Produces: an `内보내기` (Export) `UDropdownMenu` in the header. No exports consumed by other tasks.

> No unit test — this is `.vue` wiring. Gate is typecheck + lint + in-app verification (Task 6).

- [ ] **Step 1: Add the script logic**

In `front-dev-home/app/pages/afm/[tool]/[filename].vue`, extend the `<script setup lang="ts">` block. Add to the existing type imports at the top (after line 87):

```ts
import type { DropdownMenuItem } from '@nuxt/ui'
import type { CsvTable } from '~/utils/afmExport'
```

Then, after the existing loader wiring (after line 158, `const imagePending = imageLoader.pending`), add:

```ts
const summaryRows = computed(() => payload.value?.summary ?? [])
const detailRows = computed(() => payload.value?.data ?? [])
const infoEntries = computed(() => Object.entries(information.value))
const siteCount = computed(() => new Set(summaryRows.value.map(r => r.Site)).size)

const safePoint = () => selectedPoint.value.replace(/[^a-zA-Z0-9]+/g, '_') || 'point'

const downloadTable = (suffix: string, table: CsvTable) =>
  downloadCsv(`${filename.value}-${suffix}.csv`, table.headers, table.rows)

const downloadInfo = () => downloadTable('info', buildInfoCsv(information.value))
const downloadSummary = () => downloadTable('summary', buildSummaryCsv(summaryRows.value))
const downloadDetailed = () => downloadTable('detailed', buildDetailedCsv(detailRows.value))
const downloadProfile = () =>
  downloadTable(`profile-point${safePoint()}`, buildProfileCsv(profile.value))

const downloadCombined = () => {
  const content = buildCombinedContent([
    { label: 'Measurement Info', table: buildInfoCsv(information.value) },
    { label: 'Summary (by site)', table: buildSummaryCsv(summaryRows.value) },
    { label: 'Detailed Points', table: buildDetailedCsv(detailRows.value) },
    { label: `Profile (point ${selectedPoint.value || 'none'})`, table: buildProfileCsv(profile.value) }
  ])
  downloadCsvRaw(`${filename.value}-all.csv`, content)
}

const exportItems = computed<DropdownMenuItem[][]>(() => [
  [{ label: 'Download All (CSV)', icon: 'i-lucide-download', onSelect: () => downloadCombined() }],
  [
    {
      label: `Measurement Info (${infoEntries.value.length})`,
      icon: 'i-lucide-info',
      disabled: infoEntries.value.length === 0,
      onSelect: () => downloadInfo()
    },
    {
      label: `Summary (${siteCount.value} sites)`,
      icon: 'i-lucide-table',
      disabled: summaryRows.value.length === 0,
      onSelect: () => downloadSummary()
    },
    {
      label: `Detailed Points (${detailRows.value.length})`,
      icon: 'i-lucide-list',
      disabled: detailRows.value.length === 0,
      onSelect: () => downloadDetailed()
    },
    {
      label: `Profile — point ${selectedPoint.value || '—'} (${profile.value.length})`,
      icon: 'i-lucide-line-chart',
      disabled: profile.value.length === 0,
      onSelect: () => downloadProfile()
    }
  ]
])
```

- [ ] **Step 2: Add the menu to the template**

In the header actions `div` (currently lines 18-28, the `<div class="flex flex-wrap gap-2">` holding the Back button), add the dropdown **before** the Back button:

```vue
<div class="flex flex-wrap gap-2">
  <UDropdownMenu
    :items="exportItems"
    :content="{ align: 'end' }"
    :ui="{ content: 'w-64' }"
  >
    <UButton
      size="sm"
      color="neutral"
      variant="outline"
      icon="i-lucide-download"
      trailing-icon="i-lucide-chevron-down"
    >
      내보내기
    </UButton>
  </UDropdownMenu>
  <UButton
    :to="`/afm/${toolId}`"
    size="sm"
    color="neutral"
    variant="outline"
    icon="i-lucide-arrow-left"
  >
    Back to search
  </UButton>
</div>
```

- [ ] **Step 3: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors. (If it complains `buildInfoCsv`/`downloadCsv` are not defined, they are auto-imported from `app/utils`; confirm the files from Tasks 1-2 exist and re-run.)

- [ ] **Step 4: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors in `[filename].vue`.

- [ ] **Step 5: Commit**

```bash
cd front-dev-home && git add "app/pages/afm/[tool]/[filename].vue"
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add CSV export menu to measurement detail page`

---

### Task 4: Profile image (SVG) download button

**Files:**
- Modify: `front-dev-home/app/components/afm/detail/ProfileImage.vue`
- Modify: `front-dev-home/app/pages/afm/[tool]/[filename].vue` (pass `filename` prop)

**Interfaces:**
- Consumes: existing `url`/`point` props; new `filename` prop.
- Produces: a download button that saves the current SVG as `{filename}-point{point}.svg`.

> No unit test — `.vue` + network fetch. Gate is typecheck + lint + in-app verification (Task 6).

- [ ] **Step 1: Add `filename` prop and download handler**

In `front-dev-home/app/components/afm/detail/ProfileImage.vue`, replace the `<script setup>` block (lines 60-66) with:

```ts
<script setup lang="ts">
const props = defineProps<{
  url: string | null
  point: string
  filename: string
  loading?: boolean
}>()

const downloadImage = async () => {
  if (!import.meta.client || !props.url) return
  try {
    const res = await fetch(props.url)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    const safePoint = props.point.replace(/[^a-zA-Z0-9]+/g, '_') || 'point'
    link.download = `${props.filename}-point${safePoint}.svg`
    link.click()
    URL.revokeObjectURL(objectUrl)
  } catch {
    // Best-effort download; a failed fetch simply does nothing.
  }
}
</script>
```

- [ ] **Step 2: Add the download button to the header**

In `ProfileImage.vue`, replace the header's right-hand `UBadge` block (lines 17-23) so the badge and a new download button sit together:

```vue
<div class="flex items-center gap-2">
  <UBadge
    v-if="point"
    :label="`Point ${point}`"
    color="primary"
    size="xs"
    variant="subtle"
  />
  <UButton
    v-if="url"
    size="xs"
    color="neutral"
    variant="ghost"
    icon="i-lucide-download"
    aria-label="Download profile image"
    @click="downloadImage"
  />
</div>
```

(The outer header flex at line 7 already spaces the title and this group apart; this replaces only the `UBadge` on the right side.)

- [ ] **Step 3: Pass `filename` from the page**

In `front-dev-home/app/pages/afm/[tool]/[filename].vue`, update the `<AfmDetailProfileImage>` usage (currently lines 74-78) to pass the filename:

```vue
<AfmDetailProfileImage
  :url="imageUrl"
  :point="selectedPoint"
  :filename="filename"
  :loading="imagePending"
/>
```

- [ ] **Step 4: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors. (`filename` is a required prop now; the page passes it.)

- [ ] **Step 5: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/components/afm/detail/ProfileImage.vue "app/pages/afm/[tool]/[filename].vue"
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add profile-image SVG download button`

---

### Task 5: Meaningful chart PNG filenames

**Files:**
- Modify: `front-dev-home/app/components/afm/detail/HeatmapChart.vue`
- Modify: `front-dev-home/app/components/afm/detail/HistogramChart.vue`
- Modify: `front-dev-home/app/components/afm/detail/SummaryScatterChart.vue`
- Modify: `front-dev-home/app/components/afm/trend/TimeSeriesChart.vue`
- Modify: `front-dev-home/app/pages/afm/[tool]/[filename].vue` (pass `export-name` to the 3 detail charts)
- Modify: `front-dev-home/app/pages/afm/[tool]/see-together.vue` (pass `export-name` to the trend chart)

**Interfaces:**
- Consumes: `useEchart(elRef, optionRef, { exportName })` (existing `composables/useEchart.ts`).
- Produces: each chart accepts an optional `exportName?: string` prop threaded into `useEchart`.

> No unit test — one-line pass-through per chart. Gate is typecheck + lint + in-app verification (Task 6).

- [ ] **Step 1: Add `exportName` to each chart's props**

Each of the four chart components has a `defineProps<{ ... }>()` and a `useEchart(chartEl, chartOption)` call. For **each** file, (a) add `exportName?: string` to its `defineProps` object, and (b) change the `useEchart` call to pass the option.

For `HeatmapChart.vue`, change props (lines 54-57):

```ts
const props = defineProps<{
  profile: AfmProfilePoint[]
  loading?: boolean
  exportName?: string
}>()
```

and change the call (line 104):

```ts
useEchart(chartEl, chartOption, { exportName: props.exportName })
```

For `HistogramChart.vue`, `SummaryScatterChart.vue`, and `TimeSeriesChart.vue`: add `exportName?: string` to the existing `defineProps<{ ... }>()` object (keep all current props), and change their `useEchart(chartEl, chartOption)` call to `useEchart(chartEl, chartOption, { exportName: props.exportName })`. If a component destructures props (e.g. `const props = defineProps(...)`), reference `props.exportName`; if it uses `defineProps` without assignment, assign it to `const props = defineProps<{ ... }>()` first so `props.exportName` is available.

- [ ] **Step 2: Pass `export-name` from the detail page**

In `front-dev-home/app/pages/afm/[tool]/[filename].vue`, update the three chart usages (lines 63-73):

```vue
<AfmDetailSummaryScatterChart
  :summary="payload.summary"
  :export-name="`${filename}-summary-scatter`"
/>
<div class="grid gap-5 md:grid-cols-2">
  <AfmDetailHeatmapChart
    :profile="profile"
    :loading="profilePending"
    :export-name="`${filename}-heatmap`"
  />
  <AfmDetailHistogramChart
    :profile="profile"
    :loading="profilePending"
    :export-name="`${filename}-histogram`"
  />
</div>
```

- [ ] **Step 3: Pass `export-name` from see-together**

In `front-dev-home/app/pages/afm/[tool]/see-together.vue`, find the `<AfmTrendTimeSeriesChart ...>` (or equivalent trend-chart) usage and add:

```vue
:export-name="`${toolId}-trend`"
```

If the page's tool identifier is named differently (e.g. `tool` or `toolName`), use that existing variable rather than introducing a new one. Confirm with: `grep -n "toolId\|const tool\|TimeSeriesChart" app/pages/afm/[tool]/see-together.vue`.

- [ ] **Step 4: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors.

- [ ] **Step 5: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/components/afm/detail/HeatmapChart.vue app/components/afm/detail/HistogramChart.vue app/components/afm/detail/SummaryScatterChart.vue app/components/afm/trend/TimeSeriesChart.vue "app/pages/afm/[tool]/[filename].vue" "app/pages/afm/[tool]/see-together.vue"
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): give chart PNG downloads meaningful filenames`

---

### Task 6: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd front-dev-home && npm run test`
Expected: all tests pass (including the two new files).

- [ ] **Step 2: Typecheck and lint the whole app**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: no errors.

- [ ] **Step 3: In-app verification via the `verify` skill**

Invoke the project's `verify` skill (Flask mock :5050 + Nuxt SPA). On an AFM measurement detail page confirm:
  - The **내보내기** menu opens; each item shows a count; empty items are disabled.
  - **Download All (CSV)** yields one `{filename}-all.csv` with `## Measurement Info`, `## Summary (by site)`, `## Detailed Points`, `## Profile (point …)` sections; Korean values are intact in Excel (BOM works).
  - Each per-dataset item downloads its own CSV.
  - The profile image card's download button saves `{filename}-point{n}.svg`.
  - Hovering a chart shows the PNG download button; the saved file is named e.g. `{filename}-heatmap-YYYY-MM-DD.png`.

- [ ] **Step 4: Markdown lint (only if any docs changed)**

Run: `cd /Users/daeyoung/Codes/skewnono_v3_nuxt && npm run lint:md`
Expected: 0 errors. (No docs are expected to change in Tasks 1-5; skip if none did.)

---

## Self-Review

**Spec coverage:**

- CSV export — individual + combined → Tasks 1-3. ✓
- `downloadCsvRaw` extraction / single encoding site → Task 1. ✓
- Export menu (`UDropdownMenu`, counts, disabled-when-empty, filenames) → Task 3. ✓
- Profile image (SVG) download → Task 4. ✓
- Chart PNG `exportName` for the 4 charts + page wiring → Task 5. ✓
- Testing (pure builders, downloadCsv regression) → Tasks 1-2 + Task 6. ✓
- Empty-dataset / no-point-selected handling → `buildSummaryCsv([])` test, `(no data)` combined test (Task 2); `disabled` items + disabled image button (Tasks 3-4). ✓
- Out-of-scope raw TIFF/WebP → not planned (correct). ✓

Spec deviation (intentional): the spec named `composables/useAfmExport.ts`; the plan places the pure builders in `utils/afmExport.ts` instead, so they are unit-testable under `node --test` and match the repo's "pure logic in `utils/`" pattern. The page wires them directly — no composable wrapper is needed (YAGNI).

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The only conditional instruction (Task 5 Step 3, variable name in see-together) includes an exact `grep` to resolve it. ✓

**Type consistency:** `CsvTable`/`CsvSection` defined in Task 2 and consumed by the same names in Tasks 2-3; `buildCsvContent`/`downloadCsvRaw`/`downloadCsv` signatures identical across Tasks 1 and 3; `exportName` option matches `useEchart`'s existing `UseEchartOptions.exportName`. ✓
