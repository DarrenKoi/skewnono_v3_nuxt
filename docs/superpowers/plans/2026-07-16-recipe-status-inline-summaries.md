# Recipe Status Inline Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the standalone Recipe TAT, Align Fail, and Meas Fail KPI strips with compact summaries beside their ranking table titles.

**Architecture:** A pure TypeScript helper owns the summary labels and ordering, while a small presentation component owns the shared inline layout. `FailIssueView` and `RecipeTatView` format their existing API values and pass them through the helper; no backend contract or table behavior changes.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, TypeScript, Nuxt UI, Tailwind CSS, Node test runner.

## Global Constraints

- Use only the existing summary API responses for the active tool type, fab, device, and date range.
- Do not derive summary values from ranking rows or table search results.
- Preserve charts, search, sorting, pagination, copy, CSV download, row actions, row-count badges, and the TAT capped indicator.
- Render an em dash when a summary value is unavailable.
- Add no backend or API response changes.
- Preserve the repository's 2-space indentation, no-trailing-comma, and `1tbs` style.

---

## File Map

- Create `front-dev-home/app/utils/recipeStatusSummary.ts`: typed factories for ordered fail and TAT summary items.
- Create `front-dev-home/app/utils/recipeStatusSummary.test.ts`: unit coverage for labels, ordering, values, and fail emphasis.
- Create `front-dev-home/app/components/ebeam/RecipeStatusInlineSummary.vue`: compact, wrapping label-value presentation.
- Modify `front-dev-home/app/components/ebeam/FailIssueRankingTable.vue`: accept and render optional summary items.
- Modify `front-dev-home/app/components/ebeam/FailIssueView.vue`: remove KPI strips and supply Align/Meas summary items.
- Modify `front-dev-home/app/components/ebeam/RecipeTatView.vue`: remove the TAT KPI strip and render TAT summary items beside `Ranked recipes`.

### Task 1: Add the Typed Summary Model and Shared Presentation

**Files:**

- Create: `front-dev-home/app/utils/recipeStatusSummary.test.ts`
- Create: `front-dev-home/app/utils/recipeStatusSummary.ts`
- Create: `front-dev-home/app/components/ebeam/RecipeStatusInlineSummary.vue`

**Interfaces:**

- Produces: `RecipeStatusSummaryItem` with `label`, `value`, and optional `tone: 'danger'`.
- Produces: `buildFailSummaryItems(input): RecipeStatusSummaryItem[]`.
- Produces: `buildTatSummaryItems(input): RecipeStatusSummaryItem[]`.
- Produces: auto-imported `<EbeamRecipeStatusInlineSummary :items="items" />`.

- [ ] **Step 1: Write the failing summary-model test**

Create `front-dev-home/app/utils/recipeStatusSummary.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFailSummaryItems,
  buildTatSummaryItems
} from './recipeStatusSummary.ts'

test('buildFailSummaryItems keeps the agreed labels and order', () => {
  assert.deepEqual(buildFailSummaryItems({
    failLabel: 'Align fails',
    failCount: '12',
    totalMeasurements: '345',
    failRatio: '3.48%'
  }), [
    { label: 'Align fails', value: '12', tone: 'danger' },
    { label: 'Total measurements', value: '345' },
    { label: 'Fail ratio', value: '3.48%' }
  ])
})

test('buildTatSummaryItems keeps the agreed labels and order', () => {
  assert.deepEqual(buildTatSummaryItems({
    totalTat: '1h 02m 03s',
    distinctRecipes: '45',
    totalExecutions: '678',
    avgMeastime: '5s'
  }), [
    { label: 'Total TAT', value: '1h 02m 03s' },
    { label: 'Distinct recipes', value: '45' },
    { label: 'Total executions', value: '678' },
    { label: 'Avg meastime', value: '5s' }
  ])
})
```

- [ ] **Step 2: Run the focused test and confirm the missing module failure**

Run from `front-dev-home/`:

```bash
node --test app/utils/recipeStatusSummary.test.ts
```

Expected: FAIL because `./recipeStatusSummary.ts` does not exist.

- [ ] **Step 3: Implement the minimal typed factories**

Create `front-dev-home/app/utils/recipeStatusSummary.ts`:

```ts
export interface RecipeStatusSummaryItem {
  label: string
  value: string
  tone?: 'danger'
}

interface FailSummaryInput {
  failLabel: 'Align fails' | 'Meas fails'
  failCount: string
  totalMeasurements: string
  failRatio: string
}

interface TatSummaryInput {
  totalTat: string
  distinctRecipes: string
  totalExecutions: string
  avgMeastime: string
}

export const buildFailSummaryItems = (
  input: FailSummaryInput
): RecipeStatusSummaryItem[] => [
  { label: input.failLabel, value: input.failCount, tone: 'danger' },
  { label: 'Total measurements', value: input.totalMeasurements },
  { label: 'Fail ratio', value: input.failRatio }
]

export const buildTatSummaryItems = (
  input: TatSummaryInput
): RecipeStatusSummaryItem[] => [
  { label: 'Total TAT', value: input.totalTat },
  { label: 'Distinct recipes', value: input.distinctRecipes },
  { label: 'Total executions', value: input.totalExecutions },
  { label: 'Avg meastime', value: input.avgMeastime }
]
```

- [ ] **Step 4: Run the focused test and confirm both cases pass**

Run:

```bash
node --test app/utils/recipeStatusSummary.test.ts
```

Expected: PASS, 2 tests and 0 failures.

- [ ] **Step 5: Add the compact shared presentation component**

Create `front-dev-home/app/components/ebeam/RecipeStatusInlineSummary.vue`:

```vue
<template>
  <dl class="flex flex-wrap items-center gap-x-3 gap-y-1">
    <div
      v-for="item in items"
      :key="item.label"
      class="inline-flex items-baseline gap-1 whitespace-nowrap"
    >
      <dt class="text-[10px] font-medium text-(--sk-ink-muted)">
        {{ item.label }}
      </dt>
      <dd
        class="font-mono text-[11px] font-semibold tabular-nums text-(--sk-ink)"
        :class="{ 'text-(--sk-bad)': item.tone === 'danger' }"
      >
        {{ item.value }}
      </dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'

defineProps<{
  items: readonly RecipeStatusSummaryItem[]
}>()
</script>
```

- [ ] **Step 6: Run the focused test, lint the new files, and commit**

Run from `front-dev-home/`:

```bash
node --test app/utils/recipeStatusSummary.test.ts
npx eslint app/utils/recipeStatusSummary.ts app/utils/recipeStatusSummary.test.ts app/components/ebeam/RecipeStatusInlineSummary.vue
```

Expected: both commands exit 0.

Commit only Task 1 files:

```bash
git add front-dev-home/app/utils/recipeStatusSummary.ts front-dev-home/app/utils/recipeStatusSummary.test.ts front-dev-home/app/components/ebeam/RecipeStatusInlineSummary.vue
git commit -m "feat(recipe-status): add inline summary presentation"
```

### Task 2: Move Align and Meas Summaries Into Their Table Headers

**Files:**

- Modify: `front-dev-home/app/components/ebeam/FailIssueRankingTable.vue`
- Modify: `front-dev-home/app/components/ebeam/FailIssueView.vue`

**Interfaces:**

- Consumes: `RecipeStatusSummaryItem` and `buildFailSummaryItems` from Task 1.
- Adds: optional `summaryItems?: readonly RecipeStatusSummaryItem[]` prop to `FailIssueRankingTable`.

- [ ] **Step 1: Extend the generic ranking table header**

In `FailIssueRankingTable.vue`, import the summary item type:

```ts
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'
```

Add this prop after `title`:

```ts
summaryItems?: readonly RecipeStatusSummaryItem[]
```

Change the title-side wrapper to allow wrapping and render the shared summary after the row-count badge:

```vue
<div class="flex flex-wrap items-center gap-2">
  <h3 class="sk-title">
    {{ title }}
  </h3>
  <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
    {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
  </span>
  <EbeamRecipeStatusInlineSummary
    v-if="summaryItems?.length"
    :items="summaryItems"
  />
</div>
```

- [ ] **Step 2: Build the aspect-specific summary items in `FailIssueView`**

Add this import:

```ts
import { buildFailSummaryItems } from '~/utils/recipeStatusSummary'
```

Replace `alignKpiCells`, `measKpiCells`, and `placeholderKpis` with:

```ts
const alignSummaryItems = computed(() => buildFailSummaryItems({
  failLabel: 'Align fails',
  failCount: summary.value?.align_fail_count.toLocaleString() ?? '—',
  totalMeasurements: summary.value?.total_executions.toLocaleString() ?? '—',
  failRatio: summary.value ? formatPercent(summary.value.align_fail_rate) : '—'
}))

const measSummaryItems = computed(() => buildFailSummaryItems({
  failLabel: 'Meas fails',
  failCount: summary.value?.meas_fail_count.toLocaleString() ?? '—',
  totalMeasurements: summary.value?.total_executions.toLocaleString() ?? '—',
  failRatio: summary.value ? formatPercent(summary.value.meas_fail_rate) : '—'
}))
```

- [ ] **Step 3: Remove the standalone fail KPI strips and pass the summaries to the tables**

Delete both template blocks introduced by `<!-- Compact KPI strip for the active aspect -->`.

Add the following props to the existing ranking tables:

```vue
:summary-items="alignSummaryItems"
```

and:

```vue
:summary-items="measSummaryItems"
```

- [ ] **Step 4: Verify the focused fail-view change**

Run from `front-dev-home/`:

```bash
node --test app/utils/recipeStatusSummary.test.ts
npx eslint app/components/ebeam/FailIssueRankingTable.vue app/components/ebeam/FailIssueView.vue
npx nuxt typecheck
```

Expected: all commands exit 0; the unit test reports 2 passing tests.

- [ ] **Step 5: Commit only the fail-view files**

```bash
git add front-dev-home/app/components/ebeam/FailIssueRankingTable.vue front-dev-home/app/components/ebeam/FailIssueView.vue
git commit -m "refactor(recipe-status): move fail summaries into tables"
```

### Task 3: Move the TAT Summary Into the Ranked Recipes Header

**Files:**

- Modify: `front-dev-home/app/components/ebeam/RecipeTatView.vue`

**Interfaces:**

- Consumes: `buildTatSummaryItems` and `<EbeamRecipeStatusInlineSummary>` from Task 1.
- Preserves: `rankingLimit`, `filteredRankingRows`, and every table/chart interaction.

- [ ] **Step 1: Build the formatted TAT summary items**

Add this import:

```ts
import { buildTatSummaryItems } from '~/utils/recipeStatusSummary'
```

Replace `kpiCells` with:

```ts
const tatSummaryItems = computed(() => buildTatSummaryItems({
  totalTat: summary.value
    ? formatSecondsAsDuration(summary.value.total_tat_seconds)
    : '—',
  distinctRecipes: summary.value?.total_recipes.toLocaleString() ?? '—',
  totalExecutions: summary.value?.total_executions.toLocaleString() ?? '—',
  avgMeastime: summary.value
    ? formatSecondsAsDuration(Math.round(summary.value.avg_meastime))
    : '—'
}))
```

- [ ] **Step 2: Remove the standalone TAT KPI strip and render the inline summary**

Delete the template block introduced by `<!-- KPI strip -->`.

Inside the `Ranked recipes` title-side wrapper, retain the title, row-count badge, and capped indicator, then append:

```vue
<EbeamRecipeStatusInlineSummary :items="tatSummaryItems" />
```

Change that wrapper class from `flex items-center gap-2` to:

```vue
class="flex flex-wrap items-center gap-2"
```

- [ ] **Step 3: Run the complete frontend verification gate**

Run from `front-dev-home/`:

```bash
npm test
npm run lint
npm run typecheck
```

Run from the repository root:

```bash
git diff --check
```

Expected: all commands exit 0 and the Node test runner reports no failures.

- [ ] **Step 4: Verify the rendered behavior in the browser**

Start the existing Flask backend from the repository root and Nuxt frontend from `front-dev-home/`. Open a CD-SEM or HV-SEM `recipe-status` route and verify:

- Align shows three inline items beside `Align fails by recipe` and no standalone KPI strip.
- Meas shows three inline items beside `Meas fails by recipe` and no standalone KPI strip.
- TAT shows four inline items beside `Ranked recipes` and no standalone KPI strip.
- Switching overall/device scope or date range refreshes values.
- A narrow viewport wraps the title-side content without overlapping table controls.
- Search, sort, pagination, copy, CSV, row actions, and the TAT capped indicator remain present.

- [ ] **Step 5: Commit the TAT integration**

```bash
git add front-dev-home/app/components/ebeam/RecipeTatView.vue
git commit -m "refactor(recipe-status): move TAT summary into table"
```

## Completion Criteria

- The three former KPI strips are removed.
- Each ranking header contains exactly the approved summary values.
- Summary values remain server-scoped and independent of local table filtering.
- Focused unit tests, frontend lint, Nuxt typecheck, and `git diff --check` pass.
- Browser verification confirms responsive placement and unchanged table interactions.
