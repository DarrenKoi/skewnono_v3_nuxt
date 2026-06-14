# Recipe Switcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only tab bar that lets engineers switch between working-set recipes on the 열어보기 / 횡전개 / 측정이력 pages when they entered from the search-page tray.

**Architecture:** Approach A (URL-query-driven). A single self-contained component `EbeamRecipeSwitcher` reads the working set (`useRecipeSelectionSet`) and rewrites `route.query.recipe_name` via `router.replace`. The three views already react to that query through their existing `useAsyncData`, so their fetch logic is untouched. The switcher renders only when the tray-set flag `set=1` is present AND the working set has ≥ 2 recipes; otherwise it renders nothing, so row-button (single-recipe) entry looks exactly as today.

**Tech Stack:** Nuxt 4 + NuxtUI, `<script setup>` composition API, `SkNavPill` primitive, `useRecipeSelectionSet` composable, Vue Router.

**Spec:** `docs/superpowers/specs/2026-06-14-recipe-switcher-design.md`

**Testing note:** Per repo convention, `.vue` components and composables are not unit-tested — they are verified by `nuxt typecheck` + `npm run lint` + a Playwright E2E pass. The switcher has no extractable pure logic (it is a query rewrite + a visibility computed), so this plan uses typecheck/lint/E2E as its verification gates rather than `node --test` cases.

---

### Task 1: Create the `RecipeSwitcher` component

**Files:**
- Create: `front-dev-home/app/components/ebeam/RecipeSwitcher.vue` (auto-imports as `EbeamRecipeSwitcher`)

- [ ] **Step 1: Write the component**

Create `front-dev-home/app/components/ebeam/RecipeSwitcher.vue` with exactly this content:

```vue
<template>
  <nav
    v-if="show"
    aria-label="작업 세트 recipe 전환"
    class="flex flex-wrap items-center gap-1.5"
  >
    <span class="px-1 font-mono text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
      작업 세트 · {{ selected.length }}
    </span>
    <SkNavPill
      v-for="name in selected"
      :key="name"
      size="sm"
      :label="shortId(name)"
      :aria-label="name"
      :title="name"
      :active="name === activeName"
      @click="switchTo(name)"
    />
  </nav>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { readRecipeNameQuery } from '~/utils/recipeView'

const props = defineProps<{
  toolType: RecipeSearchToolType
  fab: string
}>()

const route = useRoute()
const router = useRouter()
const { selected } = useRecipeSelectionSet(props.toolType, props.fab)

// Only show when the user arrived from the tray (set=1) with 2+ recipes.
// Otherwise render nothing so single-recipe (row-button) entry is unchanged.
const show = computed(() => Boolean(route.query.set) && selected.value.length >= 2)

const activeName = computed(() => readRecipeNameQuery(route))

const shortId = (id: string) => (id.length > 28 ? `…${id.slice(-26)}` : id)

const switchTo = (name: string) => {
  if (name === activeName.value) return
  // replace (not push) so the back button returns to the list, not each tab.
  // Preserve the existing query (keeps the set=1 flag).
  router.replace({ query: { ...route.query, recipe_name: name } })
}
</script>
```

Notes for the implementer:
- `useRoute`, `useRouter`, `useRecipeSelectionSet`, `computed` are Nuxt auto-imports — do not add import statements for them.
- `SkNavPill` (from `app/components/sk/NavPill.vue`) is a global component; `:title` falls through to its single root element for the full-id tooltip. Its `active` state renders the `--sk-ink` black fill (DESIGN.md §3.5 NAVIGATE family).
- CLAUDE.md rule: `<template>` first, then `<script setup>` with composition API. The block above already follows this.

- [ ] **Step 2: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: clean (only the `ℹ Nuxt Icon server bundle mode is set to local` info line, no TS errors).

- [ ] **Step 3: Lint the new file**

Run (from `front-dev-home/`): `npx eslint app/components/ebeam/RecipeSwitcher.vue`
Expected: exit 0, no output.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeSwitcher.vue
git commit -m "feat(recipe-switcher): EbeamRecipeSwitcher working-set tab bar"
```

---

### Task 2: Wire the search-page tray to enter set mode

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeSearchView.vue` (the three `openSet*` handlers, currently near lines 244-258)

- [ ] **Step 1: Add the `set=1` flag to the three set handlers**

Find this block in `front-dev-home/app/components/ebeam/RecipeSearchView.vue`:

```ts
const openSetCompare = () => {
  if (count.value < 1) return
  router.push({ path: recipeSubpath('compare') })
}
const openSetDetail = () => {
  if (firstSelected.value) router.push(getRecipeDetailRoute(firstSelected.value))
}
const openSetLateral = () => {
  if (firstSelected.value) router.push(getLateralRoute(firstSelected.value))
}
const openSetMeasHist = () => {
  if (firstSelected.value) router.push(getMeasHistRoute(firstSelected.value))
}
```

Replace it with (adds a DRY `withSetFlag` helper; `openSetCompare` is unchanged):

```ts
const openSetCompare = () => {
  if (count.value < 1) return
  router.push({ path: recipeSubpath('compare') })
}
// Set-mode entry: tag the navigation with set=1 so the target view shows the
// working-set tab switcher. Per-row buttons (openRecipeDetail/openLateral/
// openMeasHist) intentionally omit this flag → single-recipe screen.
const withSetFlag = (target: { path: string, query: Record<string, string> }) => ({
  ...target,
  query: { ...target.query, set: '1' }
})
const openSetDetail = () => {
  if (firstSelected.value) router.push(withSetFlag(getRecipeDetailRoute(firstSelected.value)))
}
const openSetLateral = () => {
  if (firstSelected.value) router.push(withSetFlag(getLateralRoute(firstSelected.value)))
}
const openSetMeasHist = () => {
  if (firstSelected.value) router.push(withSetFlag(getMeasHistRoute(firstSelected.value)))
}
```

The existing helpers return `{ path, query: { recipe_name } }`, so `{ recipe_name }` satisfies `Record<string, string>` and the spread adds `set: '1'`.

- [ ] **Step 2: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: clean (no TS errors).

- [ ] **Step 3: Lint the changed file**

Run (from `front-dev-home/`): `npx eslint app/components/ebeam/RecipeSearchView.vue`
Expected: exit 0, no output.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeSearchView.vue
git commit -m "feat(recipe-switcher): tray opens views in set mode (set=1)"
```

---

### Task 3: Mount the switcher in the three target views

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue` (root template element, line 2)
- Modify: `front-dev-home/app/components/ebeam/RecipeLateralView.vue` (root template element, line 106)
- Modify: `front-dev-home/app/components/ebeam/RecipeMeasHistView.vue` (root template element, line 98)

All three views expose `toolType` and `fab` as props (usable directly in template). The switcher self-hides, so this is a one-line insertion at the top of each root element.

- [ ] **Step 1: RecipeOpenView — insert the switcher as the first child**

Find (line 2):

```vue
  <div class="flex h-full min-h-[640px] flex-col gap-4">
    <div class="flex shrink-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
```

Replace with:

```vue
  <div class="flex h-full min-h-[640px] flex-col gap-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab="fab"
    />
    <div class="flex shrink-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
```

- [ ] **Step 2: RecipeLateralView — insert the switcher as the first child**

Find (line 106):

```vue
  <div class="space-y-4">
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="목록으로"
```

Replace with:

```vue
  <div class="space-y-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab="fab"
    />
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="목록으로"
```

- [ ] **Step 3: RecipeMeasHistView — insert the switcher as the first child**

Find (line 98):

```vue
  <div class="space-y-4">
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="목록으로"
```

Replace with:

```vue
  <div class="space-y-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab="fab"
    />
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="목록으로"
```

- [ ] **Step 4: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: clean (no TS errors). If it reports `EbeamRecipeSwitcher` cannot be found, the component from Task 1 was not created — stop and fix Task 1.

- [ ] **Step 5: Lint the three changed files**

Run (from `front-dev-home/`):
`npx eslint app/components/ebeam/RecipeOpenView.vue app/components/ebeam/RecipeLateralView.vue app/components/ebeam/RecipeMeasHistView.vue`
Expected: exit 0, no output.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue
git commit -m "feat(recipe-switcher): mount switcher in open/lateral/meas-hist views"
```

---

### Task 4: End-to-end verification

**Files:** none (verification only). Servers run by the user in PyCharm: Flask `:5050` + Nuxt `:3000`.

- [ ] **Step 1: Confirm `.nuxt` auto-import registration**

Run (from `front-dev-home/`): `grep -n "EbeamRecipeSwitcher" .nuxt/components.d.ts`
Expected: a line registering `EbeamRecipeSwitcher` (folder prefix collapses `ebeam/RecipeSwitcher` → `EbeamRecipeSwitcher`, single `Recipe`). If absent, restart the Nuxt dev server so it regenerates the component manifest.

- [ ] **Step 2: Playwright E2E — set mode shows tabs and switches**

Drive with the Playwright MCP (save screenshots under `.playwright-mcp/screenshots/`):
1. Navigate `http://localhost:3000/ebeam/cd-sem/r3/recipe-search`.
2. Search `ABC`, check 2 rows; search `RACE`, check 2 rows → tray shows 작업 세트 · 4.
3. Click tray **열어보기** → URL is `.../recipe-search/open?recipe_name=<first>&set=1`; the switcher bar shows 4 `SkNavPill` tabs, the first active (black fill).
4. Click a different tab → URL `recipe_name` updates (still `set=1`); the page `<h1>` and content swap to that recipe. Screenshot `recipe-switcher-open.png`.
5. Browser **back** → returns to the search list (not the previous tab).
6. Repeat 열어보기 → **횡전개** and **측정이력** from the tray: each shows the switcher and swaps content on tab click. Screenshots `recipe-switcher-lateral.png`, `recipe-switcher-meashist.png`.

- [ ] **Step 3: Playwright E2E — row-button entry shows NO switcher**

1. Back on the search page, click a single row's **열어보기** button (the per-row action, not the tray).
2. Confirm the URL has no `set=1` and the switcher bar is absent (single-recipe screen, unchanged from before). Screenshot `recipe-switcher-rowentry-none.png`.

- [ ] **Step 4: Playwright E2E — reload persistence**

1. From a set-mode open page (`...&set=1`), reload the browser.
2. Confirm the switcher still shows all working-set tabs (the set is restored from `localStorage` by `useRecipeSelectionSet`).

- [ ] **Step 5: Update the build journal / spec status**

In `docs/superpowers/specs/2026-06-14-recipe-switcher-design.md`, change `Status:` to `구현 완료 (Implemented), E2E 검증 완료`. Also update `docs/superpowers/journals/2026-06-14-recipe-comparison-build.md` follow-up #2 (§9 "Recipe switcher ... deferred") to note it is now implemented.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-06-14-recipe-switcher-design.md docs/superpowers/journals/2026-06-14-recipe-comparison-build.md
git commit -m "docs(recipe-switcher): mark implemented + E2E verified"
```

---

## Self-Review

**Spec coverage:**
- D1 (tabs depend on entry path) → Task 1 `show` computed gates on `set` flag; Task 2 adds the flag only on tray entry. ✓
- D2 (`set=1` flag) → Task 2. ✓
- D3 (read-only, no ×) → Task 1 template has no remove control. ✓
- D4 (query-driven switch) → Task 1 `switchTo` → `router.replace`. ✓
- D5 (active = query recipe_name) → Task 1 `activeName` via `readRecipeNameQuery`. ✓
- D6 (single shared component) → Task 1 + Task 3 mounts it in all three. ✓
- D7 (top of view, above header) → Task 3 inserts as first child of each root. ✓
- §7 DESIGN.md (SkNavPill, --sk-ink, no rounded-full/emoji, Korean labels) → Task 1 uses SkNavPill + Korean label. ✓
- §8 testing (typecheck/lint/E2E) → Tasks 1-4 gates. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full content. ✓

**Type consistency:** `toolType: RecipeSearchToolType` and `fab: string` props match what the three views pass (`fab` is `Fab`, assignable to `string`). `withSetFlag` param `{ path: string, query: Record<string,string> }` matches the `getRecipeDetailRoute`/`getLateralRoute`/`getMeasHistRoute` return shape `{ path, query: { recipe_name: string } }`. `readRecipeNameQuery` returns `string`. Consistent. ✓
