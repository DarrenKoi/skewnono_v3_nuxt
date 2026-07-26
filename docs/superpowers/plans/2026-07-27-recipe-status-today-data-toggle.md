# Recipe Status Today-Data Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude the backend anchor date from all three Recipe 현황 daily-trend charts by default and let users include it with one page-local shared switch.

**Architecture:** Add one generic pure function that filters `{ date: string }` trend points by the backend-provided `anchor_date`. `RecipeStatusView.vue` owns the non-persisted Boolean state and passes it through named `v-model` bindings to the TAT and shared Fail views; each view derives every axis, series, ratio, and tooltip from its filtered points.

**Tech Stack:** Nuxt 4 SPA, Vue 3 `<script setup>`, TypeScript 5.9, Nuxt UI `USwitch`, ECharts 6, Node 24 built-in test runner.

## Global Constraints

- The `오늘 데이터` switch defaults to Off and resets after reload or page re-entry.
- One switch state is shared across Recipe TAT, Align Fail, and Meas Fail during the current Recipe 현황 page visit.
- Use summary `anchor_date`, never the browser wall clock, to identify today's point.
- Apply the filter only to daily-trend charts; do not change APIs, date requests, summaries, rankings, tables, or downloads.
- Do not persist the state in the URL, Nuxt `useState`, or local storage.
- Keep the existing chart card heights, Fail Bar/Line/Ratio modes, theme colors, and chart export behavior.
- Do not add a frontend dependency or a backend parameter.

---

## File Map

- Create `front-dev-home/app/utils/recipeStatusTrend.ts`: generic, immutable daily-point filtering contract.
- Create `front-dev-home/app/utils/recipeStatusTrend.test.ts`: Node test-runner coverage for Off, On, historical, missing-anchor, and immutability behavior.
- Modify `front-dev-home/app/components/ebeam/RecipeStatusView.vue`: own the shared page-local state and bind it to both child views.
- Modify `front-dev-home/app/components/ebeam/RecipeTatView.vue`: render the switch and derive all TAT trend chart data from filtered points.
- Modify `front-dev-home/app/components/ebeam/FailIssueView.vue`: render the switch on both aspect headers and derive every Fail chart mode from filtered points.
- Track this plan at `docs/superpowers/plans/2026-07-27-recipe-status-today-data-toggle.md`.

### Task 1: Pure trend-point filtering contract

**Files:**

- Create: `front-dev-home/app/utils/recipeStatusTrend.ts`
- Create: `front-dev-home/app/utils/recipeStatusTrend.test.ts`
- Track: `docs/superpowers/plans/2026-07-27-recipe-status-today-data-toggle.md`

**Interfaces:**

- Consumes: read-only arrays whose points satisfy `{ date: string }`.
- Produces:

  ```ts
  export interface RecipeStatusTrendPoint {
    date: string
  }

  export const filterRecipeStatusTrendPoints = <T extends RecipeStatusTrendPoint>(
    points: readonly T[],
    anchorDate: string | null | undefined,
    includeToday: boolean
  ): T[]
  ```

- [ ] **Step 1: Write the failing utility tests**

  Create `front-dev-home/app/utils/recipeStatusTrend.test.ts`:

  ```ts
  import { test } from 'node:test'
  import assert from 'node:assert/strict'
  import { filterRecipeStatusTrendPoints } from './recipeStatusTrend.ts'

  const points = [
    { date: '2026-07-25', value: 10 },
    { date: '2026-07-26', value: 20 },
    { date: '2026-07-27', value: 3 }
  ]

  test('filterRecipeStatusTrendPoints excludes only the anchor date by default', () => {
    assert.deepEqual(
      filterRecipeStatusTrendPoints(points, '2026-07-27', false),
      points.slice(0, 2)
    )
  })

  test('filterRecipeStatusTrendPoints includes the anchor date when enabled', () => {
    assert.deepEqual(
      filterRecipeStatusTrendPoints(points, '2026-07-27', true),
      points
    )
  })

  test('filterRecipeStatusTrendPoints keeps historical and unanchored ranges intact', () => {
    assert.deepEqual(
      filterRecipeStatusTrendPoints(points, '2026-07-30', false),
      points
    )
    assert.deepEqual(
      filterRecipeStatusTrendPoints(points, undefined, false),
      points
    )
  })

  test('filterRecipeStatusTrendPoints does not mutate its input', () => {
    const input = points.map(point => ({ ...point }))
    const before = structuredClone(input)

    filterRecipeStatusTrendPoints(input, '2026-07-27', false)

    assert.deepEqual(input, before)
  })
  ```

- [ ] **Step 2: Run the test and verify RED**

  Run from `front-dev-home/`:

  ```bash
  node --test app/utils/recipeStatusTrend.test.ts
  ```

  Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `recipeStatusTrend.ts`.

- [ ] **Step 3: Add the minimal immutable filter**

  Create `front-dev-home/app/utils/recipeStatusTrend.ts`:

  ```ts
  export interface RecipeStatusTrendPoint {
    date: string
  }

  export const filterRecipeStatusTrendPoints = <T extends RecipeStatusTrendPoint>(
    points: readonly T[],
    anchorDate: string | null | undefined,
    includeToday: boolean
  ): T[] => {
    if (includeToday || !anchorDate) return [...points]
    return points.filter(point => point.date !== anchorDate)
  }
  ```

- [ ] **Step 4: Run the utility test and verify GREEN**

  Run:

  ```bash
  node --test app/utils/recipeStatusTrend.test.ts
  ```

  Expected: four passing tests, zero failures.

- [ ] **Step 5: Commit the filtering contract and plan**

  ```bash
  git add docs/superpowers/plans/2026-07-27-recipe-status-today-data-toggle.md front-dev-home/app/utils/recipeStatusTrend.ts front-dev-home/app/utils/recipeStatusTrend.test.ts
  git diff --cached --check
  git commit -m "feat(recipe-status): define today trend filtering"
  ```

### Task 2: Shared state and Recipe TAT chart

**Files:**

- Modify: `front-dev-home/app/components/ebeam/RecipeStatusView.vue:39-52,67-91`
- Modify: `front-dev-home/app/components/ebeam/RecipeTatView.vue:143-159,285-303,393-488`
- Test: `front-dev-home/app/utils/recipeStatusTrend.test.ts`

**Interfaces:**

- Consumes: `filterRecipeStatusTrendPoints(points, anchorDate, includeToday)` from Task 1.
- Produces: named child model `includeToday: boolean` and parent-owned `ref(false)`.

- [ ] **Step 1: Add the parent-owned page-local model**

  In `RecipeStatusView.vue`, bind both kept-alive views to the same state:

  ```vue
  <EbeamRecipeTatView
    v-if="activeTab === 'tat'"
    v-model:include-today="includeToday"
    :fab="fab"
    :tool-label="toolLabel"
    :tool-type="toolType"
  />
  <EbeamFailIssueView
    v-else
    v-model:include-today="includeToday"
    :fab="fab"
    :tool-label="toolLabel"
    :tool-type="toolType"
    :section="activeTab"
  />
  ```

  Add local state near the tab state:

  ```ts
  const includeToday = ref(false)
  ```

  Do not use `useState` or route query state.

- [ ] **Step 2: Add the TAT named model and switch**

  In `RecipeTatView.vue`, declare:

  ```ts
  const includeToday = defineModel<boolean>('includeToday', { required: true })
  ```

  Change the Daily TAT header to preserve the title on the left and add the
  switch on the right:

  ```vue
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-2">
      <UIcon
        name="i-lucide-trending-up"
        class="h-4 w-4 text-(--sk-ink-muted)"
      />
      <h3 class="sk-title">
        Daily TAT trend
      </h3>
    </div>
    <USwitch
      v-model="includeToday"
      size="sm"
      label="오늘 데이터"
      class="shrink-0"
    />
  </div>
  ```

- [ ] **Step 3: Derive all TAT trend behavior from filtered points**

  Import the Task 1 utility and add:

  ```ts
  const visibleTrendPoints = computed(() => filterRecipeStatusTrendPoints(
    trendPoints.value,
    summary.value?.anchor_date,
    includeToday.value
  ))
  ```

  Replace every TAT trend-only `trendPoints.value` lookup in the tooltip,
  x-axis data, x-axis interval calculation, and line-series data with
  `visibleTrendPoints.value`. Do not change bar-chart or table data.

- [ ] **Step 4: Verify the TAT integration**

  Run from `front-dev-home/`:

  ```bash
  node --test app/utils/recipeStatusTrend.test.ts
  npm run typecheck
  npm run lint
  ```

  Expected: all commands exit 0. Type checking proves the named `v-model`,
  `defineModel`, generic point type, and ECharts option wiring agree.

- [ ] **Step 5: Commit the parent and TAT integration**

  ```bash
  git add front-dev-home/app/components/ebeam/RecipeStatusView.vue front-dev-home/app/components/ebeam/RecipeTatView.vue
  git diff --cached --check
  git commit -m "feat(recipe-status): toggle today's TAT point"
  ```

### Task 3: Align Fail and Meas Fail chart integration

**Files:**

- Modify: `front-dev-home/app/components/ebeam/FailIssueView.vue:110-201,270-282,369-370,426-568`
- Test: `front-dev-home/app/utils/recipeStatusTrend.test.ts`

**Interfaces:**

- Consumes: parent `v-model:include-today`, Task 1 filter, summary `anchor_date`.
- Produces: filtered Align/Meas x-axis, Bar/Line values, Ratio values, total-measurement baseline, and tooltips.

- [ ] **Step 1: Add the Fail named model and both visible switches**

  Declare:

  ```ts
  const includeToday = defineModel<boolean>('includeToday', { required: true })
  ```

  In the Align chart header, wrap its chart-type radiogroup and switch:

  ```vue
  <div class="flex flex-wrap items-center justify-end gap-3">
    <div
      role="radiogroup"
      aria-label="Align fail chart type"
      class="inline-flex items-center gap-0.5 rounded-md bg-zinc-100/80 p-0.5 dark:bg-zinc-800/70"
    >
      <button
        v-for="chartOption in CHART_TYPES"
        :key="chartOption.value"
        type="button"
        role="radio"
        :aria-checked="chartType === chartOption.value"
        class="inline-flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition-colors"
        :class="chartType === chartOption.value
          ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="chartType = chartOption.value"
      >
        <UIcon
          :name="chartOption.icon"
          class="h-3.5 w-3.5"
        />
        {{ chartOption.label }}
      </button>
    </div>
    <USwitch
      v-model="includeToday"
      size="sm"
      label="오늘 데이터"
      class="shrink-0"
    />
  </div>
  ```

  Use the same wrapper in the Meas chart header with this complete radiogroup:

  ```vue
  <div class="flex flex-wrap items-center justify-end gap-3">
    <div
      role="radiogroup"
      aria-label="Meas fail chart type"
      class="inline-flex items-center gap-0.5 rounded-md bg-zinc-100/80 p-0.5 dark:bg-zinc-800/70"
    >
      <button
        v-for="chartOption in CHART_TYPES"
        :key="chartOption.value"
        type="button"
        role="radio"
        :aria-checked="chartType === chartOption.value"
        class="inline-flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition-colors"
        :class="chartType === chartOption.value
          ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="chartType = chartOption.value"
      >
        <UIcon
          :name="chartOption.icon"
          class="h-3.5 w-3.5"
        />
        {{ chartOption.label }}
      </button>
    </div>
    <USwitch
      v-model="includeToday"
      size="sm"
      label="오늘 데이터"
      class="shrink-0"
    />
  </div>
  ```

- [ ] **Step 2: Build one filtered point array**

  Import the Task 1 utility and add next to `trendPoints`:

  ```ts
  const visibleTrendPoints = computed(() => filterRecipeStatusTrendPoints(
    trendPoints.value,
    summary.value?.anchor_date,
    includeToday.value
  ))
  ```

  Derive `xAxisDates` from `visibleTrendPoints`.

- [ ] **Step 3: Keep every Fail series and tooltip index aligned**

  In `buildTrendOption`, resolve the tooltip point from
  `visibleTrendPoints.value[idx]`.

  Build both options from the filtered array:

  ```ts
  const alignTrendOption = computed<EChartsOption>(() =>
    buildTrendOption(
      'Align fails',
      visibleTrendPoints.value.map(point => point.align_fail_count),
      sk.value.series,
      visibleTrendPoints.value.map(point => point.exec_count)
    ))

  const measTrendOption = computed<EChartsOption>(() =>
    buildTrendOption(
      'Meas fails',
      visibleTrendPoints.value.map(point => point.meas_fail_count),
      sk.value.brand,
      visibleTrendPoints.value.map(point => point.exec_count)
    ))
  ```

  This single source must feed Bar, Line, Ratio, total-measurement baseline,
  x-axis labels, and tooltips.

- [ ] **Step 4: Verify the Fail integration**

  Run from `front-dev-home/`:

  ```bash
  node --test app/utils/recipeStatusTrend.test.ts
  npm run typecheck
  npm run lint
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit the Fail integration**

  ```bash
  git add front-dev-home/app/components/ebeam/FailIssueView.vue
  git diff --cached --check
  git commit -m "feat(recipe-status): toggle today's fail points"
  ```

### Task 4: Full regression and running-app verification

**Files:**

- Verify only: all files from Tasks 1-3.

**Interfaces:**

- Consumes: completed feature.
- Produces: fresh automated and running-app evidence.

- [ ] **Step 1: Run all frontend gates**

  Run from `front-dev-home/`:

  ```bash
  npm test
  npm run typecheck
  npm run lint
  ```

  Expected: each command exits 0 with no test failures, type errors, or lint
  errors.

- [ ] **Step 2: Run repository diff guards**

  Run from the repository root:

  ```bash
  npm run lint:md
  git diff --check
  git status --short --branch
  ```

  Expected: Markdown lint and diff check exit 0. Status may still show the
  pre-existing `.remember` and OpenWiki changes, but no intended feature file
  remains uncommitted.

- [ ] **Step 3: Verify the running app**

  Open
  `http://localhost:3000/ebeam/cd-sem/R3/recipe-status?tab=tat` with the mock
  backend available.

  Confirm:

  1. Daily TAT trend shows `오늘 데이터` Off on first entry and omits the
     `anchor_date` x-axis point.
  2. Turning it On adds that point without a network request.
  3. Align Fail and Meas Fail retain the On state and show the same switch.
  4. Turning it Off in a Fail tab also updates TAT after switching back.
  5. Fail Bar, Line, and Ratio modes all continue to render with aligned
     tooltips and the whole-measurement baseline where applicable.
  6. Reloading restores Off.
  7. Date-range and device selection still refresh the existing API-backed
     data while the display toggle remains page-local.

- [ ] **Step 4: Confirm commit scope**

  Run:

  ```bash
  git log --oneline --decorate -4
  git show --stat --oneline HEAD
  git status --short --branch
  ```

  Verify that feature commits contain only the plan, utility, tests, and the
  three Recipe 현황 components. Do not stage or commit the unrelated
  `.remember` or OpenWiki changes.
