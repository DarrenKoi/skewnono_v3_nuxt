# AFM Points-Table Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add free-text search, a localStorage-persisted column picker, pagination (25/page), and summary tiles to the AFM measurement-points table, keeping the existing point-chip filter.

**Architecture:** Pure logic (column derivation/ordering/labels, row filtering, summary, page slice) goes in a new `utils/afmPointsTable.ts` unit-tested with `node --test`; `MeasurementPointsTable.vue` gains a `UInput` search, a `USelectMenu` column picker, summary tiles, and `UPagination`, wired to the util. No backend change.

**Tech Stack:** Nuxt 4 + NuxtUI v4.6.1 (`UInput`, `USelectMenu`, `UPagination`), TypeScript, Node's built-in test runner.

## Global Constraints

- Frontend root `front-dev-home/`; run `npm` there. Tests: `node --test app/utils/afmPointsTable.test.ts`. Gates: `npm run typecheck`, `npm run lint`.
- Column order: preferred (the current 8, present ones only) → `(nm)` columns → others, each group in first-seen order. Labels: known overrides (`measurement_point`→`Site`, `Point No`→`#`, `X (um)`→`X (μm)`, `Y (um)`→`Y (μm)`, `Left_H (nm)`→`Left_H`, `Right_H (nm)`→`Right_H`, `Ref_H (nm)`→`Ref_H`), else title-cased.
- Search matches a case-insensitive substring in any *visible* column only.
- Pagination is client-side, 25/page; `page` resets to 1 on any filter/search/point change; `pagePointRows` clamps out-of-range pages.
- Column selection persists to `localStorage` key `skewnono:afm.pointColumns`, client-guarded + try/catch (like `useAfmCart`). Stored keys absent from current data are ignored; if the intersection is empty, fall back to defaults ∩ present.
- Keep the existing point-chip filter and the `update:selectedPoint` emit. Drop CSV (Sub-project A covers it).
- Pure util: no DOM/Nuxt runtime imports (type-only `AfmDetailRow`). The `.vue` relies on Nuxt auto-import for util runtime exports; `import type` for its types.
- Work on `main`; commit per task; do NOT push. Tree has UNRELATED concurrent user WIP (`.remember/`, `docs/` deletions, a "chat" feature). Each task `git add`s ONLY its explicit files — never `git add -A`/`git add .`/`git stash`.
- Every commit message ends with:

  ```text
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NHWMRqfxSYaLcagApFG1tB
  ```

---

### Task 1: Pure points-table logic (`utils/afmPointsTable.ts`)

**Files:**
- Create: `front-dev-home/app/utils/afmPointsTable.ts`
- Test: `front-dev-home/app/utils/afmPointsTable.test.ts`

**Interfaces:**
- Consumes: `AfmDetailRow` (type-only).
- Produces: `PointColumn`, `DEFAULT_POINT_COLUMN_KEYS`, `derivePointColumns(rows)`, `filterPointRows(rows, selectedPoint, search, visibleKeys)`, `PointsSummary`, `pointsSummary(rows)`, `pagePointRows(rows, page, pageSize)`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/afmPointsTable.test.ts`:

```ts
// Pure-logic tests for afmPointsTable. Run: node --test app/utils/afmPointsTable.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  derivePointColumns,
  filterPointRows,
  pointsSummary,
  pagePointRows,
  DEFAULT_POINT_COLUMN_KEYS
} from './afmPointsTable.ts'

const rows = [
  { measurement_point: '1_UL', 'Point No': 1, 'X (um)': 10, 'State': 'OK', Valid: true, 'CD (nm)': 5, Mileage: 3 },
  { measurement_point: '1_UL', 'Point No': 2, 'X (um)': 11, 'State': 'NG', Valid: false, 'CD (nm)': 6, Mileage: 4 },
  { measurement_point: '2_UR', 'Point No': 1, 'X (um)': 20, 'State': 'OK', Valid: true, 'CD (nm)': 7, Mileage: 5 }
] as any

test('derivePointColumns: preferred first, then (nm), then others; labels applied', () => {
  const cols = derivePointColumns(rows)
  const keys = cols.map(c => c.key)
  // preferred present ones keep their order and come first
  assert.equal(keys[0], 'measurement_point')
  assert.ok(keys.indexOf('CD (nm)') > keys.indexOf('State'))       // nm after preferred
  assert.ok(keys.indexOf('Mileage') > keys.indexOf('CD (nm)'))     // others after nm
  const labelOf = (k: string) => cols.find(c => c.key === k)!.label
  assert.equal(labelOf('measurement_point'), 'Site')
  assert.equal(labelOf('X (um)'), 'X (μm)')
  assert.equal(labelOf('Mileage'), 'Mileage')                       // title-cased unknown
})

test('filterPointRows: point filter only', () => {
  assert.equal(filterPointRows(rows, '1_UL', '', DEFAULT_POINT_COLUMN_KEYS).length, 2)
  assert.equal(filterPointRows(rows, '', '', DEFAULT_POINT_COLUMN_KEYS).length, 3)
})

test('filterPointRows: search is case-insensitive over visible columns only', () => {
  // 'ng' matches State on row 2
  assert.equal(filterPointRows(rows, '', 'ng', ['State']).length, 1)
  // searching a value that lives only in a HIDDEN column returns nothing
  assert.equal(filterPointRows(rows, '', '3', ['State']).length, 0)     // Mileage 3 hidden
  assert.equal(filterPointRows(rows, '', '3', ['Mileage']).length, 1)   // Mileage visible
})

test('filterPointRows: point + search combined', () => {
  assert.equal(filterPointRows(rows, '1_UL', 'ok', ['State']).length, 1)
})

test('pointsSummary: total and valid', () => {
  assert.deepEqual(pointsSummary(rows), { total: 3, valid: 2 })
  assert.deepEqual(pointsSummary([]), { total: 0, valid: 0 })
})

test('pagePointRows: slices and clamps', () => {
  const many = Array.from({ length: 60 }, (_, i) => ({ n: i })) as any
  assert.equal(pagePointRows(many, 1, 25).length, 25)
  assert.equal(pagePointRows(many, 3, 25).length, 10)   // last partial page
  assert.equal(pagePointRows(many, 99, 25).length, 10)  // clamped to last page
  assert.equal(pagePointRows([], 1, 25).length, 0)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/afmPointsTable.test.ts`
Expected: FAIL — `Cannot find module './afmPointsTable.ts'`.

- [ ] **Step 3: Write `afmPointsTable.ts`**

Create `front-dev-home/app/utils/afmPointsTable.ts`:

```ts
// Pure helpers for the AFM measurement-points table (column derivation, filtering,
// summary, paging). No DOM/Nuxt imports so they run under `node --test`.
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

export interface PointColumn {
  key: string
  label: string
}

export const DEFAULT_POINT_COLUMN_KEYS: string[] = [
  'measurement_point', 'Point No', 'X (um)', 'Y (um)',
  'Left_H (nm)', 'Right_H (nm)', 'Ref_H (nm)', 'State'
]

const LABEL_OVERRIDES: Record<string, string> = {
  measurement_point: 'Site',
  'Point No': '#',
  'X (um)': 'X (μm)',
  'Y (um)': 'Y (μm)',
  'Left_H (nm)': 'Left_H',
  'Right_H (nm)': 'Right_H',
  'Ref_H (nm)': 'Ref_H'
}

const humanizeKey = (key: string): string =>
  LABEL_OVERRIDES[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

export const derivePointColumns = (rows: AfmDetailRow[]): PointColumn[] => {
  const seen = new Set<string>()
  const keys: string[] = []
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (!seen.has(k)) {
        seen.add(k)
        keys.push(k)
      }
    }
  }
  const preferred = DEFAULT_POINT_COLUMN_KEYS.filter(k => seen.has(k))
  const rest = keys.filter(k => !DEFAULT_POINT_COLUMN_KEYS.includes(k))
  const nm = rest.filter(k => k.includes('(nm)'))
  const others = rest.filter(k => !k.includes('(nm)'))
  return [...preferred, ...nm, ...others].map(k => ({ key: k, label: humanizeKey(k) }))
}

export const filterPointRows = (
  rows: AfmDetailRow[],
  selectedPoint: string,
  search: string,
  visibleKeys: string[]
): AfmDetailRow[] => {
  let out = selectedPoint
    ? rows.filter(r => r.measurement_point === selectedPoint)
    : rows
  const q = search.trim().toLowerCase()
  if (q) {
    out = out.filter(r =>
      visibleKeys.some(k =>
        String((r as Record<string, unknown>)[k] ?? '').toLowerCase().includes(q)
      )
    )
  }
  return out
}

export interface PointsSummary {
  total: number
  valid: number
}

export const pointsSummary = (rows: AfmDetailRow[]): PointsSummary => ({
  total: rows.length,
  valid: rows.reduce((n, r) => n + (r.Valid === true ? 1 : 0), 0)
})

export const pagePointRows = (
  rows: AfmDetailRow[],
  page: number,
  pageSize: number
): AfmDetailRow[] => {
  if (rows.length === 0 || pageSize <= 0) return []
  const maxPage = Math.max(1, Math.ceil(rows.length / pageSize))
  const p = Math.min(Math.max(1, Math.floor(page) || 1), maxPage)
  const start = (p - 1) * pageSize
  return rows.slice(start, start + pageSize)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/afmPointsTable.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors in `utils/afmPointsTable.ts`.

- [ ] **Step 6: Commit**

```bash
cd front-dev-home && git add app/utils/afmPointsTable.ts app/utils/afmPointsTable.test.ts
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add pure points-table column/filter/paging helpers`

---

### Task 2: Upgrade `MeasurementPointsTable.vue`

**Files:**
- Modify: `front-dev-home/app/components/afm/detail/MeasurementPointsTable.vue`

**Interfaces:**
- Consumes (auto-imported): `derivePointColumns`, `filterPointRows`, `pointsSummary`, `pagePointRows`, `DEFAULT_POINT_COLUMN_KEYS`; `chipClass` from `~/utils/chipClass`; types `PointColumn` via `import type`; `AfmDetailRow` type.

> No unit test — `.vue` wiring. Gate: `npm run typecheck` + `npm run lint`, plus in-app verification (Task 3).

- [ ] **Step 1: Replace the component with the upgraded version**

Replace the entire contents of `front-dev-home/app/components/afm/detail/MeasurementPointsTable.vue` with:

```vue
<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-0', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-target"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Measurement points
          </h2>
          <span class="sk-meta tabular-nums">
            ({{ filteredRows.length }} / {{ data.length }})
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            v-for="point in availablePoints"
            :key="point"
            type="button"
            class="inline-flex h-6 items-center rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
            :class="chipClass(selectedPoint === point)"
            @click="$emit('update:selectedPoint', point)"
          >
            {{ point }}
          </button>
          <button
            v-if="selectedPoint"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-full px-2 text-[11px] text-(--sk-ink-muted) ring-1 ring-zinc-200 hover:bg-zinc-50 dark:ring-zinc-700 dark:hover:bg-zinc-800"
            @click="$emit('update:selectedPoint', '')"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
            All
          </button>
        </div>
      </div>
    </template>

    <div class="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-4 py-2.5 dark:border-zinc-800/60">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        size="xs"
        placeholder="Search rows…"
        class="w-44"
      />
      <USelectMenu
        v-model="visibleKeys"
        :items="columnItems"
        value-key="value"
        multiple
        size="xs"
        icon="i-lucide-columns-3"
        placeholder="Columns"
        class="min-w-40"
        :search-input="{ placeholder: 'Filter columns…' }"
      />
      <div class="ml-auto flex items-center gap-3 sk-meta tabular-nums">
        <span>Total <b class="text-(--sk-ink)">{{ summary.total }}</b></span>
        <span>Valid <b class="text-(--sk-ink)">{{ summary.valid }}</b></span>
        <span>Cols <b class="text-(--sk-ink)">{{ visibleColumns.length }}</b></span>
      </div>
    </div>

    <div
      v-if="filteredRows.length === 0"
      class="px-4 py-10 text-center sk-body"
    >
      No measurement rows
    </div>
    <template v-else>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px] font-mono">
          <thead class="bg-zinc-50/95 text-(--sk-ink-muted) dark:bg-zinc-900/90">
            <tr>
              <th
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-2.5 py-1.5 text-right sk-label first:text-left"
              >
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in pagedRows"
              :key="i"
              class="border-t border-zinc-100 transition-colors hover:bg-zinc-50/80 dark:border-zinc-800/60 dark:hover:bg-zinc-800/30"
            >
              <td
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-2.5 py-1 text-right sk-value-num first:text-left"
              >
                {{ formatCell(row[col.key]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        v-if="filteredRows.length > PAGE_SIZE"
        class="flex justify-center border-t border-zinc-100 px-4 py-2 dark:border-zinc-800/60"
      >
        <UPagination
          v-model:page="page"
          :total="filteredRows.length"
          :items-per-page="PAGE_SIZE"
          :sibling-count="1"
          size="xs"
        />
      </div>
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import { chipClass } from '~/utils/chipClass'

const props = defineProps<{
  data: AfmDetailRow[]
  availablePoints: string[]
  selectedPoint: string
}>()

defineEmits<{
  (event: 'update:selectedPoint', point: string): void
}>()

const PAGE_SIZE = 25
const STORAGE_KEY = 'skewnono:afm.pointColumns'

const search = ref('')
const page = ref(1)
const visibleKeys = ref<string[]>([])

const allColumns = computed(() => derivePointColumns(props.data))
const columnItems = computed(() => allColumns.value.map(c => ({ label: c.label, value: c.key })))
const visibleColumns = computed(() => allColumns.value.filter(c => visibleKeys.value.includes(c.key)))

const loadStoredKeys = (): string[] | null => {
  if (!import.meta.client) return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === 'string') : null
  } catch {
    return null
  }
}

let initialized = false
watch(allColumns, (cols) => {
  if (initialized || cols.length === 0) return
  const present = new Set(cols.map(c => c.key))
  const stored = (loadStoredKeys() ?? []).filter(k => present.has(k))
  visibleKeys.value = stored.length
    ? stored
    : DEFAULT_POINT_COLUMN_KEYS.filter(k => present.has(k))
  initialized = true
}, { immediate: true })

watch(visibleKeys, (keys) => {
  if (!import.meta.client) return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
  } catch {
    // ignore persistence failures (private mode, quota)
  }
}, { deep: true })

const filteredRows = computed(() =>
  filterPointRows(props.data, props.selectedPoint, search.value, visibleKeys.value)
)
const pagedRows = computed(() => pagePointRows(filteredRows.value, page.value, PAGE_SIZE))
const summary = computed(() => pointsSummary(filteredRows.value))

watch([() => props.selectedPoint, search, visibleKeys], () => {
  page.value = 1
}, { deep: true })

const formatCell = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors attributable to `MeasurementPointsTable.vue`. Pre-existing `RadiusChart.vue` errors are unrelated. (If `USelectMenu`'s `v-model` complains about the value-key array type, confirm `visibleKeys` is `ref<string[]>` and `columnItems` values are strings — the `value-key="value"` binding yields a `string[]` model.)

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors in `MeasurementPointsTable.vue`. If ESLint reports auto-fixable stylistic issues, run `npx eslint --fix app/components/afm/detail/MeasurementPointsTable.vue` and re-lint.

- [ ] **Step 4: Commit**

```bash
cd front-dev-home && git add app/components/afm/detail/MeasurementPointsTable.vue
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add search/column-picker/pagination to points table`

---

### Task 3: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Frontend suite + gates**

Run: `cd front-dev-home && npm run test && npm run typecheck && npm run lint`
Expected: `afmPointsTable.test.ts` passes with the rest; typecheck shows only pre-existing unrelated `RadiusChart.vue` errors; lint clean for the changed files. (`chatMarkdown.test.ts` / `relativeTime.test.ts` failures are the user's unrelated chat WIP, not this work.)

- [ ] **Step 2: In-app verification (verify skill)**

With Flask (`:5050`) and Nuxt (`:3000`) running, open an AFM detail page with detailed rows and confirm:
  - Search narrows the visible rows (case-insensitive) and the count updates.
  - The column picker adds/removes columns; the choice **persists across a page reload** (localStorage).
  - Pagination appears when > 25 rows and pages through; page resets to 1 when search/point/columns change.
  - Summary tiles (Total / Valid / Cols) update with the filter.
  - The point-chip filter still filters to one point and "All" clears it.

- [ ] **Step 3: Markdown lint (only if docs changed)**

Run `npm run lint:md` from repo root only if any docs changed (none expected in Tasks 1-2).

---

## Self-Review

**Spec coverage:**

- Free-text search over visible columns → Task 1 `filterPointRows` (+ hidden-column test); Task 2 `UInput`. ✓
- Column picker over derived columns, persisted → Task 1 `derivePointColumns`; Task 2 `USelectMenu` + localStorage load/save with present-key intersection + default fallback. ✓
- Pagination 25/page, reset on filter change, clamp → Task 1 `pagePointRows` (+ clamp test); Task 2 `UPagination` + page-reset watcher. ✓
- Summary tiles (total, valid, cols) → Task 1 `pointsSummary`; Task 2 tiles. ✓
- Keep point-chip filter + emit; drop CSV → point chips unchanged in Task 2; no CSV added. ✓
- Column ordering/labels (preferred → nm → others; overrides + title-case) → Task 1 `derivePointColumns` + test. ✓
- Edge cases (empty data, 0 results, localStorage unavailable, stored keys absent, page out of range) → Task 1 guards + Task 2 client-guards/fallback. ✓

**Placeholder scan:** No TBD/TODO; complete code in every step. ✓

**Type consistency:** `PointColumn`/`PointsSummary`/`DEFAULT_POINT_COLUMN_KEYS` defined in Task 1 and consumed by the same names in Task 2; `derivePointColumns`/`filterPointRows`/`pointsSummary`/`pagePointRows` signatures match between util, tests, and component. The `update:selectedPoint` emit and `chipClass` usage are preserved from the original component. ✓
