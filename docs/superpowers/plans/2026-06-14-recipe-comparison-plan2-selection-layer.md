# Recipe Comparison — Plan 2: Selection Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent multi-select "working set" of recipes, seeded from checkboxes on the existing search page, with a sticky tray exposing the four actions (열어보기 / 횡전개 / 측정이력 / 비교하기).

**Architecture:** `useRecipeSelectionSet(toolType, fab)` mirrors `useRecipeRecentSearches` exactly — a `useState` ref shared across SPA navigation + an `effectScope` watcher persisting to `localStorage`, scoped per `(toolType, fab)`. The selection survives query changes because it lives in shared state, not the result list. The search page gains a checkbox column and a `SearchSelectTray`; tray actions navigate using the existing route helpers (비교하기 → new compare route; the other three open the **first** selected recipe this pass).

**Tech Stack:** Nuxt 4 `useState`/`effectScope`, NuxtUI `UCheckbox`/`UButton`, TypeScript.

---

## Key decisions (confirm before coding)

- Working set is scoped per `(toolType, fab)` — same `localStorage`-keying scheme as recent searches. Switching fab/tool shows a different set.
- This pass: only 비교하기 consumes the whole set. 열어보기/횡전개/측정이력 open the **first** selected recipe via the existing single-recipe routes (the in-page switcher is a later fast-follow).
- The compare page reads the working set from the composable (shared state), so 비교하기 navigates with **no recipe names in the URL**.

---

### Task 1: `useRecipeSelectionSet` composable

**Files:**
- Create: `front-dev-home/app/composables/useRecipeSelectionSet.ts`

- [ ] **Step 1: Write the composable**

Copy the persistence machinery from `useRecipeRecentSearches.ts` (same `readJSON`/`writeJSON`/`effectScope` pattern) so behavior is consistent.

```typescript
// Per-(toolType, fab) persistent recipe working set, persisted to localStorage.
// Mirrors useRecipeRecentSearches: useState shares one ref across client-side
// navigation; a watcher in a detached effect scope persists to localStorage so the
// set survives full reloads. The set powers compare (this pass) and, later, a
// recipe switcher in open/lateral/meas-hist.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.selection.${toolType}.${fab || 'ALL'}`

const persistenceScope = effectScope(true)
const persistenceWatchers = new Set<string>()

function readJSON<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return fallback
    return parsed as T
  } catch {
    return fallback
  }
}

function writeJSON(key: string, value: unknown) {
  if (typeof window === 'undefined') return
  try {
    if (Array.isArray(value) && value.length === 0) {
      window.localStorage.removeItem(key)
    } else {
      window.localStorage.setItem(key, JSON.stringify(value))
    }
  } catch { /* noop */ }
}

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`
  const key = storageKey(toolType, fab)

  const selected = useState<string[]>(
    `recipe-search:selection:${scope}`,
    () => readJSON<string[]>(key, [])
  )

  if (!persistenceWatchers.has(scope)) {
    persistenceWatchers.add(scope)
    persistenceScope.run(() => {
      watch(selected, next => writeJSON(key, next), { flush: 'sync' })
    })
  }

  const has = (name: string) => selected.value.includes(name)

  const add = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed || has(trimmed)) return
    selected.value = [...selected.value, trimmed]
  }

  const remove = (name: string) => {
    selected.value = selected.value.filter(existing => existing !== name)
  }

  const toggle = (name: string) => {
    has(name) ? remove(name) : add(name)
  }

  const clear = () => {
    selected.value = []
  }

  const count = computed(() => selected.value.length)

  return { selected, has, add, remove, toggle, clear, count }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors referencing `useRecipeSelectionSet.ts`.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useRecipeSelectionSet.ts
git commit -m "feat(recipe-compare): persistent working-set composable"
```

---

### Task 2: `SearchSelectTray` component

**Files:**
- Create: `front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue`

Component auto-imports as `<EbeamRecipeCompareSearchSelectTray>` (folder-prefix convention — do not repeat the folder name in the filename).

- [ ] **Step 1: Write the component**

```vue
<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-y-4 opacity-0"
    leave-active-class="transition duration-150 ease-in"
    leave-to-class="translate-y-4 opacity-0"
  >
    <div
      v-if="selected.length"
      class="fixed inset-x-0 bottom-4 z-40 mx-auto w-full max-w-[1100px] px-4"
    >
      <div class="dashboard-surface flex flex-col gap-3 rounded-2xl border border-(--sk-brand)/40 p-3 shadow-lg sm:flex-row sm:items-center">
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          <span class="shrink-0 text-[11px] font-semibold text-(--sk-brand)">
            🧺 작업 세트 · {{ selected.length }}
          </span>
          <span
            v-for="name in selected"
            :key="name"
            class="inline-flex max-w-[220px] items-center gap-1 rounded-full bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[10.5px] text-zinc-700 dark:text-zinc-200"
          >
            <span class="truncate">{{ name }}</span>
            <button
              type="button"
              class="rounded-full p-0.5 text-zinc-400 transition hover:bg-zinc-300 hover:text-zinc-900 dark:hover:bg-zinc-600 dark:hover:text-zinc-50"
              :aria-label="`Remove ${name}`"
              @click="emit('remove', name)"
            >
              <UIcon name="i-lucide-x" class="h-3 w-3" />
            </button>
          </span>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            label="선택 비우기"
            @click="emit('clear')"
          />
        </div>

        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <UButton size="sm" color="neutral" variant="outline" icon="i-lucide-file-search" label="열어보기" @click="emit('open')" />
          <UButton size="sm" color="neutral" variant="outline" icon="i-lucide-network" label="횡전개" @click="emit('lateral')" />
          <UButton size="sm" color="neutral" variant="outline" icon="i-lucide-history" label="측정이력" @click="emit('measHist')" />
          <UButton size="sm" color="primary" variant="solid" icon="i-lucide-scale" label="비교하기" @click="emit('compare')" />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
defineProps<{
  selected: string[]
}>()

const emit = defineEmits<{
  remove: [name: string]
  clear: []
  open: []
  lateral: []
  measHist: []
  compare: []
}>()
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue
git commit -m "feat(recipe-compare): SearchSelectTray sticky working-set bar"
```

---

### Task 3: Wire selection into `RecipeSearchView`

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeSearchView.vue`

- [ ] **Step 1: Add the composable + helpers in `<script setup>`**

After the existing `useRecipeRecentSearches(...)` destructure (around line 17-22), add:

```typescript
const { selected, has, toggle, remove, clear, count } = useRecipeSelectionSet(props.toolType, props.fab)

const togglePageSelection = () => {
  const pageNames = pagedRows.value.map(row => row.recipe_name)
  const allSelected = pageNames.length > 0 && pageNames.every(name => has(name))
  if (allSelected) {
    pageNames.forEach(name => remove(name))
  } else {
    pageNames.forEach((name) => { if (!has(name)) toggle(name) })
  }
}

const firstSelected = computed(() => selected.value[0] ?? '')

const openSetCompare = () => {
  if (count.value < 1) return
  router.push({ path: recipeSubpath('compare') })
}
const openSetDetail = () => { if (firstSelected.value) router.push(getRecipeDetailRoute(firstSelected.value)) }
const openSetLateral = () => { if (firstSelected.value) router.push(getLateralRoute(firstSelected.value)) }
const openSetMeasHist = () => { if (firstSelected.value) router.push(getMeasHistRoute(firstSelected.value)) }
```

(`recipeSubpath`, `getRecipeDetailRoute`, `getLateralRoute`, `getMeasHistRoute`, `router`, `pagedRows` already exist in this file.)

- [ ] **Step 2: Add a select column to the table definition**

Change the `columns` definition (around line 200) from:

```typescript
const columns: TableColumn<RecipeSearchRow>[] = [
  { accessorKey: 'recipe_name', header: 'recipe_name', size: 520 },
  { id: 'open', header: '', size: 400 }
]
```

to:

```typescript
const columns: TableColumn<RecipeSearchRow>[] = [
  { id: 'select', header: '', size: 36 },
  { accessorKey: 'recipe_name', header: 'recipe_name', size: 500 },
  { id: 'open', header: '', size: 380 }
]
```

- [ ] **Step 3: Add the header + cell slots and the tray to the template**

In the `<UTable>` (around line 466), add a `#select-header` and `#select-cell` slot just before the existing `#recipe_name-cell` slot:

```vue
        <template #select-header>
          <UCheckbox
            :model-value="pagedRows.length > 0 && pagedRows.every(row => has(row.recipe_name))"
            aria-label="현재 페이지 전체 선택"
            @update:model-value="togglePageSelection"
          />
        </template>

        <template #select-cell="{ row }">
          <UCheckbox
            :model-value="has(row.original.recipe_name)"
            :aria-label="`${row.original.recipe_name} 선택`"
            @update:model-value="toggle(row.original.recipe_name)"
          />
        </template>
```

Then, immediately before the closing `</div>` of the outer `mx-auto` wrapper (the last line of the template, after the results `</section>` and its wrapping `</div>`), add the tray:

```vue
    <EbeamRecipeCompareSearchSelectTray
      :selected="selected"
      @remove="remove"
      @clear="clear"
      @compare="openSetCompare"
      @open="openSetDetail"
      @lateral="openSetLateral"
      @meas-hist="openSetMeasHist"
    />
```

- [ ] **Step 4: Add a discoverability hint near the search box**

In the `searchHelp`-rendering line (around line 337, the `<span>{{ searchHelp }}</span>`), no change needed; instead add a one-time hint under the recent-searches block. Find the `mt-2 flex flex-wrap items-center justify-between` help row (around line 336) and replace its content with:

```vue
        <div class="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-(--sk-ink-muted)">
          <span>{{ searchHelp }} · <span class="text-(--sk-ink-muted)">체크하면 여러 recipe를 한 번에 열거나 비교할 수 있습니다.</span></span>
          <span
            v-if="canSearch && refinedCount > 0"
            class="tabular-nums"
          >
            {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} / {{ refinedCount.toLocaleString() }}
          </span>
        </div>
```

- [ ] **Step 5: Typecheck + lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeSearchView.vue
git commit -m "feat(recipe-compare): checkbox column + working-set tray on search"
```

---

### Task 4: Manual verification (persistence across searches)

> Plan 3 builds the compare page; the 비교하기 button 404s until then. This task verifies selection + persistence only. The other three actions navigate to existing pages.

- [ ] **Step 1: Run the app and exercise the flow**

Ensure Flask (:5050) and Nuxt (:3000) are running (user runs both in PyCharm). Then, with Playwright MCP, save screenshots under `.playwright-mcp/screenshots/`:

1. Navigate to `http://localhost:3000/ebeam/cd-sem/r3/recipe-search`.
2. Search `ABC`, check 2 rows.
3. Change the search to `RACE`, check 2 more rows.
4. Confirm the tray shows **4** chips (the `ABC` picks survived the query change).
5. Click "열어보기" → lands on the first selected recipe's open page.
6. Reload the page → tray still shows the set (localStorage persistence).

- [ ] **Step 2: Record the result**

Confirm in the conversation: selection accumulates across queries, survives reload, and tray actions navigate. Note any issues.

- [ ] **Step 3: Commit (screenshots are git-ignored; nothing to commit unless fixes were made)**

If fixes were needed, commit them with a `fix(recipe-compare): ...` message.

---

## Done when

- Checking rows builds a set that survives query changes and reloads.
- The tray shows chips, clear, and four actions; 열어보기/횡전개/측정이력 open the first selected recipe.
- `npm run typecheck` + `npm run lint` clean.
