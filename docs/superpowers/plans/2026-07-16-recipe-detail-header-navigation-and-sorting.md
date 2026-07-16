# Recipe Detail Header, Navigation, and Sorting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align all three Recipe detail headers, add persistent quick navigation among them, move Recipe-wide counts into the parameter table header, and make every parameter column sortable with SEQ ascending by default.

**Architecture:** Keep the existing detail views and hand-written parameter table. Put sorting and navigation-item construction in pure TypeScript helpers covered by Node tests, then keep Vue components focused on rendering. Reuse `EbeamMetaBar`, `EbeamFeatureHeader`, `RECIPE_ROW_ACTIONS`, `recipeDetailRoute`, and the existing Recipe Status inline-summary presentation.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup>`, TypeScript, Nuxt UI 4, Node test runner, ESLint.

## Global Constraints

- Remove `CD-SEM · R3`, `HV-CD-SEM · R3`, and equivalent tool/Fab identity from all three Recipe detail headers only.
- Keep Recipe API endpoints, request behavior, and response shapes unchanged.
- Keep `recipe_name` and optional `set=1` while hopping among `open`, `lateral`, and `meas-hist`.
- Keep the existing history-back behavior and Recipe-search fallback route.
- Render Recipe-wide point totals in the parameter table header, never as repeated row columns.
- Default parameter ordering is `SEQ` ascending; sorting must preserve source-index selection.
- Preserve unrelated worktree changes and stage only files belonging to each task.

---

## File Map

- Create `front-dev-home/app/utils/recipeOpenTable.ts`: pure stable sorting, sort-state transitions, and summary items.
- Create `front-dev-home/app/utils/recipeOpenTable.test.ts`: Node tests for the parameter-table model.
- Modify `front-dev-home/app/components/ebeam/recipeOpen/IdpTable.vue`: sortable headers, sorted rows, source-index selection, and inline summary.
- Modify `front-dev-home/app/components/ebeam/RecipeOpenView.vue`: compact header, summary inputs, and shared navigation.
- Create `front-dev-home/app/utils/recipeDetailNavigation.test.ts`: Node tests for active navigation and `set=1` preservation.
- Modify `front-dev-home/app/utils/recipeView.ts`: tested navigation-item builder using existing route/action definitions.
- Create `front-dev-home/app/components/ebeam/RecipeDetailNav.vue`: larger back button and three quick-hop actions.
- Modify `front-dev-home/app/components/ebeam/RecipeLateralView.vue`: shared navigation and no tool/Fab eyebrow.
- Modify `front-dev-home/app/components/ebeam/RecipeMeasHistView.vue`: shared navigation and no tool/Fab eyebrow.

### Task 1: Sortable Parameter Table and Inline Recipe Counts

**Files:**

- Create: `front-dev-home/app/utils/recipeOpenTable.ts`
- Create: `front-dev-home/app/utils/recipeOpenTable.test.ts`
- Modify: `front-dev-home/app/components/ebeam/recipeOpen/IdpTable.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue`

**Interfaces:**

- Consumes: `IdpImageInfoRow` and `RecipeStatusSummaryItem`.
- Produces: `RecipeOpenSortKey`, `RecipeOpenSortDirection`, `DEFAULT_RECIPE_OPEN_SORT`, `sortRecipeOpenRows`, `nextRecipeOpenSort`, and `buildRecipeOpenSummaryItems`.
- `sortRecipeOpenRows` returns `{ row: IdpImageInfoRow, sourceIndex: number }[]`; only `sourceIndex` may update `selectedIdpIndex`.

- [ ] **Step 1: Write the failing pure-helper tests**

Create `front-dev-home/app/utils/recipeOpenTable.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { IdpImageInfoRow } from '../composables/useRecipeSearchApi.ts'
import {
  buildRecipeOpenSummaryItems,
  nextRecipeOpenSort,
  sortRecipeOpenRows
} from './recipeOpenTable.ts'

const row = (overrides: Partial<IdpImageInfoRow> = {}): IdpImageInfoRow => ({
  Parameter: 'P1', img_add1: '', img_add2: '', img_meas1: '', img_meas2: '',
  SEQ: 1, Last_SEQ: 3, Region: 1, image_add3: '', Addressing: 'No',
  Mother_Para: '—', Double_Addressing: false, Meas_Counting: 1,
  dnumber_removed: 0, ...overrides
})

test('defaults to stable SEQ ascending order and preserves source indices', () => {
  const sorted = sortRecipeOpenRows([
    row({ Parameter: 'third', SEQ: 3 }),
    row({ Parameter: 'first-a', SEQ: 1 }),
    row({ Parameter: 'first-b', SEQ: 1 }),
    row({ Parameter: 'second', SEQ: 2 })
  ])
  assert.deepEqual(sorted.map(item => item.row.Parameter), [
    'first-a', 'first-b', 'second', 'third'
  ])
  assert.deepEqual(sorted.map(item => item.sourceIndex), [1, 2, 3, 0])
})

test('compares text numerically and booleans as false then true', () => {
  const rows = [
    row({ Parameter: 'P10', Double_Addressing: true }),
    row({ Parameter: 'P2', Double_Addressing: false })
  ]
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'Parameter', 'asc').map(item => item.row.Parameter),
    ['P2', 'P10']
  )
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'Double_Addressing', 'asc')
      .map(item => item.row.Double_Addressing),
    [false, true]
  )
})

test('supports descending numeric order', () => {
  const rows = [row({ SEQ: 1 }), row({ SEQ: 3 }), row({ SEQ: 2 })]
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'SEQ', 'desc').map(item => item.row.SEQ),
    [3, 2, 1]
  )
})

test('toggles the active key and starts a new key ascending', () => {
  assert.deepEqual(nextRecipeOpenSort('SEQ', 'asc', 'SEQ'), {
    key: 'SEQ', direction: 'desc'
  })
  assert.deepEqual(nextRecipeOpenSort('SEQ', 'desc', 'Parameter'), {
    key: 'Parameter', direction: 'asc'
  })
})

test('builds the agreed table-header counts', () => {
  assert.deepEqual(buildRecipeOpenSummaryItems(42, 6), [
    { label: '측정 포인트', value: '42' },
    { label: 'Align 포인트', value: '6' }
  ])
})
```

- [ ] **Step 2: Run the focused test and verify RED**

From `front-dev-home/`, run:

```bash
node --test app/utils/recipeOpenTable.test.ts
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `recipeOpenTable.ts`.

- [ ] **Step 3: Add the minimal pure implementation**

Create `front-dev-home/app/utils/recipeOpenTable.ts`:

```ts
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'

export type RecipeOpenSortKey = Extract<keyof IdpImageInfoRow,
  | 'Parameter' | 'SEQ' | 'Region' | 'Addressing' | 'Mother_Para'
  | 'Double_Addressing' | 'Meas_Counting' | 'dnumber_removed'
>
export type RecipeOpenSortDirection = 'asc' | 'desc'
export const DEFAULT_RECIPE_OPEN_SORT = {
  key: 'SEQ' as RecipeOpenSortKey,
  direction: 'asc' as RecipeOpenSortDirection
}

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
const compare = (
  left: IdpImageInfoRow[RecipeOpenSortKey],
  right: IdpImageInfoRow[RecipeOpenSortKey]
) => {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  if (typeof left === 'boolean' && typeof right === 'boolean') {
    return Number(left) - Number(right)
  }
  return collator.compare(String(left), String(right))
}

export const sortRecipeOpenRows = (
  rows: readonly IdpImageInfoRow[],
  key: RecipeOpenSortKey = DEFAULT_RECIPE_OPEN_SORT.key,
  direction: RecipeOpenSortDirection = DEFAULT_RECIPE_OPEN_SORT.direction
) => {
  const multiplier = direction === 'asc' ? 1 : -1
  return rows.map((row, sourceIndex) => ({ row, sourceIndex })).sort((a, b) => (
    compare(a.row[key], b.row[key]) * multiplier || a.sourceIndex - b.sourceIndex
  ))
}

export const nextRecipeOpenSort = (
  currentKey: RecipeOpenSortKey,
  currentDirection: RecipeOpenSortDirection,
  requestedKey: RecipeOpenSortKey
) => ({
  key: requestedKey,
  direction: (currentKey === requestedKey && currentDirection === 'asc'
    ? 'desc'
    : 'asc') as RecipeOpenSortDirection
})

export const buildRecipeOpenSummaryItems = (
  measurementPointCount: number,
  alignPointCount: number
): RecipeStatusSummaryItem[] => [
  { label: '측정 포인트', value: measurementPointCount.toLocaleString() },
  { label: 'Align 포인트', value: alignPointCount.toLocaleString() }
]
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run `node --test app/utils/recipeOpenTable.test.ts`.

Expected: 5 tests pass, 0 fail.

- [ ] **Step 5: Wire sorting and summary into `IdpTable.vue`**

Use props `rows`, `measurementPointCount`, and `alignPointCount`. Initialize
`sortKey`/`sortDirection` from `DEFAULT_RECIPE_OPEN_SORT`; compute
`displayedRows = sortRecipeOpenRows(props.rows, sortKey.value,
sortDirection.value)` and `summaryItems = buildRecipeOpenSummaryItems(...)`.
Define these exact columns:

```ts
const columns: readonly { key: RecipeOpenSortKey, label: string }[] = [
  { key: 'Parameter', label: 'Parameter' },
  { key: 'SEQ', label: 'SEQ' },
  { key: 'Region', label: 'Region' },
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Mother_Para', label: 'Mother' },
  { key: 'Double_Addressing', label: 'Double' },
  { key: 'Meas_Counting', label: 'Cnt' },
  { key: 'dnumber_removed', label: 'd#_rm' }
]
```

Use `nextRecipeOpenSort` for clicks. Return `none`, `ascending`, or
`descending` from `ariaSort`; return `i-lucide-arrow-up-down`,
`i-lucide-arrow-up-narrow-wide`, or `i-lucide-arrow-down-wide-narrow` from
`sortIcon`. Render each header as a button with `:aria-sort`, icon, and label.
Render the summary beside the title:

```vue
<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
  <p class="mt-0.5 sk-title">파라미터 목록 · {{ rows.length }}</p>
  <EbeamRecipeStatusInlineSummary :items="summaryItems" />
</div>
```

Render `v-for="item in displayedRows"`; replace every existing `row.FIELD`
binding in the eight cells with `item.row.FIELD`. Compare selection to
`item.sourceIndex` and set `selectedIndex = item.sourceIndex` on click. Keep
the existing cells, pills, `SEQ/Last_SEQ` display, hint, and Align button
unchanged.

- [ ] **Step 6: Pass counts from `RecipeOpenView.vue`**

```vue
<EbeamRecipeOpenIdpTable
  v-model:selected-index="selectedIdpIndex"
  :rows="idpImageRows"
  :measurement-point-count="waferMpRows.length"
  :align-point-count="data.wafer_align_info.length"
  @open-align="alignOpen = true"
/>
```

Keep `statCells` through Task 1 because the old header still renders it. Task 2
deletes both the old statistics card and `statCells` in the same change.

- [ ] **Step 7: Verify and commit Task 1**

Run from `front-dev-home/`:

```bash
node --test app/utils/recipeOpenTable.test.ts
npm run lint
npm run typecheck
```

Expected: 5 tests pass; lint and typecheck exit 0. Then commit only Task 1:

```bash
git add front-dev-home/app/utils/recipeOpenTable.ts front-dev-home/app/utils/recipeOpenTable.test.ts front-dev-home/app/components/ebeam/recipeOpen/IdpTable.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue
git commit -m "feat: sort recipe parameter details"
```

### Task 2: Shared Detail Navigation and Identity-Free Headers

**Files:**

- Create: `front-dev-home/app/utils/recipeDetailNavigation.test.ts`
- Modify: `front-dev-home/app/utils/recipeView.ts`
- Create: `front-dev-home/app/components/ebeam/RecipeDetailNav.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeLateralView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeMeasHistView.vue`

**Interfaces:**

- Consumes: `RecipeDetailScreen`, `RECIPE_ROW_ACTIONS`, `recipeDetailRoute`, and `useHistoryBack`.
- Produces: `buildRecipeDetailNavItems(toolType, fab, recipeName, activeScreen, setFlag)` and `EbeamRecipeDetailNav` props `{ toolType, fab, recipeName, activeScreen }`.
- Every hop contains `recipe_name`; it contains `set: '1'` only when the current query has exactly `set=1`.

- [ ] **Step 1: Write the failing navigation-model tests**

Create `front-dev-home/app/utils/recipeDetailNavigation.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildRecipeDetailNavItems } from './recipeView.ts'

test('creates all detail hops and marks the active screen', () => {
  const items = buildRecipeDetailNavItems(
    'cd-sem', 'R3', 'RECIPE-01', 'lateral', undefined
  )
  assert.deepEqual(items.map(item => item.label), [
    '열어 보기', '횡전개', '측정 이력'
  ])
  assert.deepEqual(items.map(item => item.active), [false, true, false])
  assert.deepEqual(items[0]?.to, {
    path: '/ebeam/cd-sem/r3/recipe-search/open',
    query: { recipe_name: 'RECIPE-01' }
  })
})

test('preserves the work-set flag on every hop', () => {
  const items = buildRecipeDetailNavItems(
    'hv-sem', 'R4', 'HV-RECIPE', 'open', '1'
  )
  assert.deepEqual(items.map(item => item.to.query), [
    { recipe_name: 'HV-RECIPE', set: '1' },
    { recipe_name: 'HV-RECIPE', set: '1' },
    { recipe_name: 'HV-RECIPE', set: '1' }
  ])
})
```

- [ ] **Step 2: Run the focused test and verify RED**

From `front-dev-home/`, run:

```bash
node --test app/utils/recipeDetailNavigation.test.ts
```

Expected: FAIL because `buildRecipeDetailNavItems` is not exported.

- [ ] **Step 3: Add the tested builder to `recipeView.ts`**

Append after `RECIPE_ROW_ACTIONS`:

```ts
export const buildRecipeDetailNavItems = (
  toolType: string,
  fab: string,
  recipeName: string,
  activeScreen: RecipeDetailScreen,
  setFlag: unknown
) => RECIPE_ROW_ACTIONS.map((action) => {
  const target = recipeDetailRoute(toolType, fab, action.screen, recipeName)
  return {
    ...action,
    active: action.screen === activeScreen,
    to: setFlag === '1'
      ? { ...target, query: { ...target.query, set: '1' } }
      : target
  }
})
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run `node --test app/utils/recipeDetailNavigation.test.ts`.

Expected: 2 tests pass, 0 fail.

- [ ] **Step 5: Create `RecipeDetailNav.vue`**

Create `front-dev-home/app/components/ebeam/RecipeDetailNav.vue`:

```vue
<script setup lang="ts">
import {
  buildRecipeDetailNavItems,
  type RecipeDetailScreen
} from '~/utils/recipeView'

const props = defineProps<{
  toolType: string
  fab: string
  recipeName: string
  activeScreen: RecipeDetailScreen
}>()

const route = useRoute()
const backRoute = computed(() => (
  `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`
))
const { goBack } = useHistoryBack(backRoute)
const items = computed(() => buildRecipeDetailNavItems(
  props.toolType,
  props.fab,
  props.recipeName,
  props.activeScreen,
  route.query.set
))
</script>

<template>
  <nav
    aria-label="Recipe 상세 화면 이동"
    class="flex flex-wrap items-center gap-2"
  >
    <UButton
      size="md"
      color="neutral"
      variant="outline"
      icon="i-lucide-arrow-left"
      label="돌아가기"
      class="rounded-full font-semibold"
      :to="backRoute"
      @click.prevent="goBack"
    />
    <div class="inline-flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60">
      <UButton
        v-for="item in items"
        :key="item.screen"
        size="sm"
        color="neutral"
        :variant="item.active ? 'solid' : 'ghost'"
        :icon="item.icon"
        :label="item.label"
        :to="item.to"
        :aria-current="item.active ? 'page' : undefined"
        class="font-semibold"
        @click="item.active && $event.preventDefault()"
      />
    </div>
  </nav>
</template>
```

- [ ] **Step 6: Replace the `open` title/stat block with `EbeamMetaBar`**

Keep `EbeamRecipeSwitcher`, then render:

```vue
<EbeamMetaBar
  :title="titleRecipeName || 'Recipe 상세'"
  :subtitle="data ? formatTimestamp(data.timestamp) : ''"
>
  <template #actions>
    <EbeamRecipeDetailNav
      :tool-type="toolType"
      :fab="fab"
      :recipe-name="recipeName"
      active-screen="open"
    />
  </template>
</EbeamMetaBar>
```

Delete the old back button, `{{ toolLabel }} · {{ fab }}` paragraph,
`fac_id · tool_category · timestamp` paragraph, and statistics card. Do not
set `eyebrow`; retain `formatTimestamp` for the subtitle. Delete the now-unused
`statCells` computed value here.

- [ ] **Step 7: Update `RecipeLateralView.vue`**

Replace the standalone back button with:

```vue
<EbeamRecipeDetailNav
  :tool-type="toolType"
  :fab="fab"
  :recipe-name="recipeName"
  active-screen="lateral"
/>
```

Remove the `EbeamFeatureHeader` eyebrow prop. Keep title, subtitle, and stats.
Delete the now-unused `backRoute` and `goBackToList` declarations.

- [ ] **Step 8: Update `RecipeMeasHistView.vue`**

Replace the standalone back button with:

```vue
<EbeamRecipeDetailNav
  :tool-type="toolType"
  :fab="fab"
  :recipe-name="recipeName"
  active-screen="meas-hist"
/>
```

Remove the `EbeamFeatureHeader` eyebrow prop. Keep title, subtitle, and stats.
Delete the now-unused `backRoute` and `goBackToList` declarations.

- [ ] **Step 9: Verify and commit Task 2**

From `front-dev-home/`, run:

```bash
node --test app/utils/recipeDetailNavigation.test.ts
node --test app/utils/recipeOpenTable.test.ts
npm run lint
npm run typecheck
```

Expected: 2 navigation tests and 5 table tests pass; lint and typecheck exit 0.
Then commit only Task 2:

```bash
git add front-dev-home/app/utils/recipeDetailNavigation.test.ts front-dev-home/app/utils/recipeView.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue
git commit -m "feat: add recipe detail quick navigation"
```

### Task 3: Full Regression and Requirement Verification

**Files:**

- Verify: all files changed in Tasks 1 and 2
- No new production files

**Interfaces:**

- Consumes: the completed sortable-table and shared-navigation implementations.
- Produces: fresh verification evidence and a requirement-by-requirement handoff.

- [ ] **Step 1: Run the complete frontend test suite**

From `front-dev-home/`, run:

```bash
npm test
```

Expected: all Node tests pass with 0 failures, including the 7 new tests.

- [ ] **Step 2: Run the complete frontend quality gate**

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Expected: all three commands exit 0. Report any non-fatal Nuxt build warning
verbatim; do not describe an error as passing.

- [ ] **Step 3: Check diff hygiene and scope**

From the repository root, run:

```bash
git diff --check
git status --short
git diff "$IMPLEMENTATION_BASE"..HEAD -- front-dev-home/app/utils/recipeOpenTable.ts front-dev-home/app/utils/recipeOpenTable.test.ts front-dev-home/app/utils/recipeDetailNavigation.test.ts front-dev-home/app/utils/recipeView.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue front-dev-home/app/components/ebeam/recipeOpen/IdpTable.vue
```

Expected: `git diff --check` prints nothing; status and diff show no unrelated
file staged or modified by this work.

- [ ] **Step 4: Verify every requested behavior**

Use the existing development servers and inspect `open`, `lateral`, and
`meas-hist` for one Recipe. Confirm:

- No detail header contains `CD-SEM · R3`, `HV-CD-SEM · R3`, or another
  tool/Fab identity.
- `돌아가기` is larger and immediately followed by `열어 보기`, `횡전개`, and
  `측정 이력`.
- The current destination is visibly active and has `aria-current="page"`.
- Hopping preserves `recipe_name`; work-set entry also preserves `set=1`.
- `측정 포인트` and `Align 포인트` appear beside `파라미터 목록 · N`, and the
  former right-side statistics card is absent.
- The table first appears in SEQ ascending order.
- Every data-column header toggles direction and shows the correct icon.
- Clicking a row after sorting updates the right-side detail for that exact row.
- The `Align 정보` popup still opens.

If the in-app browser is unavailable, record the limitation and rely on the
full automated checks plus source/diff inspection. Do not claim a browser
check occurred.

- [ ] **Step 5: Commit only if verification required a scoped fix**

After rerunning the command that previously failed, stage only the corrected
task files and commit:

```bash
git add front-dev-home/app/utils/recipeOpenTable.ts front-dev-home/app/utils/recipeOpenTable.test.ts front-dev-home/app/utils/recipeDetailNavigation.test.ts front-dev-home/app/utils/recipeView.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue front-dev-home/app/components/ebeam/recipeOpen/IdpTable.vue
git commit -m "fix: complete recipe detail navigation"
```

If no verification fix was needed, do not create an empty commit.
