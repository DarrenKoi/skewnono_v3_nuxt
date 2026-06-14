# Device-Statistics D22 — Plan 2: Descriptive View (all fabs)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For a selected set of devices, show a comparable per-device **point-count outlier count** and a shared `device → recipe → parameter` drill-down (기타 expanded), so an analyst can spot over-measuring devices. Works identically for every fab.

**Architecture:** A pure shared view-model (`deviceDrill.ts`: `DrillDevice` + adapters) feeds a dumb slideover (`DrillSlideover.vue`). A new `profile.vue` page consumes the existing device cart, fetches `recipe-params` (Plan 1) for the selected lots, runs `detectDeviceOutliers` (Plan 1) per device, and renders a sortable device table + the drill-down. Plan 3 reuses the same `DrillDevice` shape and slideover with a different adapter.

**Tech Stack:** Nuxt 4 + NuxtUI (`USlideover`, `UTable`, `UButton`), `useAsyncData` + `$fetch`, pure TS adapters tested with `node --test`.

**Depends on:** Plan 1 (`fetchRecipeParams`, `detectDeviceOutliers`).

---

## ⚠️ Key decisions baked into this plan (confirm before executing)

1. **Scope = the selected device set, not the full 2000-row table.** Computing outliers per device needs that device's 100–200 recipes; doing it for every row is infeasible in Phase 1. The descriptive view therefore analyzes the devices the user has put in the **existing cart** (`useDeviceCart`), which is also what makes "comparable across devices" meaningful. *(Phase 2/3 office alternative: a backend summary endpoint that precomputes per-device counts so the full table can show them — noted, not built here.)*
2. **Placement = a new sibling page `device-statistics/profile.vue`,** reached from the cart with a second proceed action (parallel to the existing `comparison.vue`). Keeps the legacy bin-format comparison page untouched and gives the descriptive view a clean surface.
3. **Device-row unit = count of outlier *parameters* in the device** (D22 open item ②), matching the user's "counts of … outlier in the device." The drill-down groups those outliers under their recipes.

If you'd rather the counts live on the main index table (needs the summary endpoint) or fold into `comparison.vue`, redirect here first.

## 🎨 UI consistency requirement (user directive)

Match the existing UI style exactly — do **not** introduce a new visual language. Concretely:

- **Header:** use `<EbeamFeatureHeader>` with `eyebrow="CD-SEM"`, `:title`, `:subtitle`, and a `#actions` slot holding a back button — mirror `device-statistics/comparison.vue` (lines 3–35).
- **Surfaces:** wrap cards in `class="dashboard-surface rounded-2xl"`; use `UCard` with `:ui="{ body: 'p-0 sm:p-0' }"` for tables, exactly like `index.vue`.
- **Slideover:** `USlideover` with `:ui="{ content: 'w-[80vw] sm:max-w-[80vw]' }"` + a `#body` slot + a summary card — mirror `components/ebeam/RecipeDetailSlideover.vue` (lines 1–68).
- **Tokens:** use the semantic CSS vars (`text-(--sk-ink)`, `text-(--sk-ink-muted)`, `text-(--sk-ink-subtle)`, `bg-(--sk-surface)`, `border-(--sk-border)`, `bg-(--sk-accent)`) — never raw `text-zinc-*` for muted text (memory: dark-mode semantic ink tokens). Match the `Matrix.vue` table header style (`font-mono text-[11px] uppercase tracking-wide text-(--sk-ink-muted)`).
- **Empty state:** mirror `comparison.vue` lines 37–60 (icon tile + title + desc + CTA).
- **Loading / error:** mirror `MeasurementRulesView.vue` lines 35–50 (spinner row / rose error text).

Every new component in this plan already follows these; keep it that way through any edits.

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `front-dev-home/app/utils/deviceDrill.ts` | `DrillDevice`/`DrillRecipe`/`DrillParameter` types + `toOutlierDrill` adapter | Create |
| `front-dev-home/app/utils/deviceDrill.test.ts` | Adapter unit tests | Create |
| `front-dev-home/app/components/ebeam/devstat/DrillSlideover.vue` | Dumb `device→recipe→parameter` slideover (auto-imports as `EbeamDevstatDrillSlideover`) | Create |
| `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/profile.vue` | Selected-set outlier table + drill | Create |
| `front-dev-home/app/components/ebeam/CompareCart.vue` | Add "프로파일 분석" proceed action | Modify |

> **Component naming (memory: nuxt-component-folder-prefix):** the folder `devstat/` prefixes the auto-import name, so the file is `DrillSlideover.vue` → `<EbeamDevstatDrillSlideover>`. Do **not** name it `DevstatDrillSlideover.vue`.

---

## Task 1: Shared `DrillDevice` view-model + outlier adapter (TDD)

The slideover must be reusable by Plan 3, so it consumes a normalized shape it does not compute. Plan 2 supplies the outlier adapter; Plan 3 adds a violation adapter producing the same shape.

**Files:**
- Create: `front-dev-home/app/utils/deviceDrill.test.ts`
- Create: `front-dev-home/app/utils/deviceDrill.ts`

- [ ] **Step 1: Write the failing tests**

Create `front-dev-home/app/utils/deviceDrill.test.ts`:

```ts
// Pure tests for the drill view-model adapters. Run: node --test app/utils/deviceDrill.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toOutlierDrill } from './deviceDrill.ts'
import type { RecipeInput } from './ruleEngine.ts'
import { detectDeviceOutliers } from './outlierDetect.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000', recipe_id, fac_id: 'R3', ctn_desc: '', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 'EV', memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

test('outlier drill marks the over-threshold param and its recipe', () => {
  const recipes = [recipe('A', [10, 10, 10, 10]), recipe('B', [50, 10])]
  const result = detectDeviceOutliers(recipes) // median 10, threshold 20
  const drill = toOutlierDrill('R000', 'dev desc', recipes, result)

  assert.equal(drill.lot_cd, 'R000')
  assert.equal(drill.ctn_desc, 'dev desc')
  assert.equal(drill.flagged_param_count, 1)
  assert.equal(drill.flagged_recipe_count, 1)

  const recB = drill.recipes.find(r => r.recipe_id === 'B')!
  assert.equal(recB.flagged, true)
  assert.equal(recB.flagged_count, 1)
  const p0 = recB.parameters.find(p => p.name === 'P_0')!
  assert.equal(p0.flagged, true)
  assert.equal(p0.note, '> 20')          // threshold note
  const p1 = recB.parameters.find(p => p.name === 'P_1')!
  assert.equal(p1.flagged, false)

  const recA = drill.recipes.find(r => r.recipe_id === 'A')!
  assert.equal(recA.flagged, false)
})

test('no outliers → every recipe unflagged, counts zero', () => {
  const recipes = [recipe('A', [10, 10]), recipe('B', [10, 10])]
  const drill = toOutlierDrill('R000', '', recipes, detectDeviceOutliers(recipes))
  assert.equal(drill.flagged_param_count, 0)
  assert.equal(drill.flagged_recipe_count, 0)
  assert.ok(drill.recipes.every(r => !r.flagged))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd front-dev-home && node --test app/utils/deviceDrill.test.ts`
Expected: FAIL — `Cannot find module './deviceDrill.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/deviceDrill.ts`:

```ts
// Shared drill-down view-model (D22). Both the descriptive (outlier) and
// prescriptive (cap-violation) surfaces normalize into DrillDevice so a single
// slideover renders both. Adapters are pure + unit-tested.
import type { RecipeInput } from './ruleEngine'
import type { DeviceOutlierResult } from './outlierDetect'

export interface DrillParameter {
  name: string
  point_count: number
  flagged: boolean
  note?: string // why it was flagged, e.g. "> 20" (outlier) or "cap 10" (violation)
}

export interface DrillRecipe {
  recipe_id: string
  flagged: boolean
  total_params: number
  flagged_count: number
  parameters: DrillParameter[]
}

export interface DrillDevice {
  lot_cd: string
  ctn_desc: string
  recipes: DrillRecipe[]
  flagged_recipe_count: number
  flagged_param_count: number
}

/** Descriptive adapter — within-device point-count outliers (Plan 1). */
export const toOutlierDrill = (
  lot_cd: string,
  ctn_desc: string,
  recipes: RecipeInput[],
  result: DeviceOutlierResult
): DrillDevice => {
  const flaggedKey = new Set(result.outliers.map(o => `${o.recipe_id} ${o.name}`))
  const drillRecipes: DrillRecipe[] = recipes.map((r) => {
    const parameters: DrillParameter[] = r.parameters.map((p) => {
      const flagged = flaggedKey.has(`${r.recipe_id} ${p.name}`)
      return { name: p.name, point_count: p.point_count, flagged, note: flagged ? `> ${result.threshold}` : undefined }
    })
    const flagged_count = parameters.filter(p => p.flagged).length
    return { recipe_id: r.recipe_id, flagged: flagged_count > 0, total_params: parameters.length, flagged_count, parameters }
  })
  return {
    lot_cd,
    ctn_desc,
    recipes: drillRecipes,
    flagged_recipe_count: drillRecipes.filter(r => r.flagged).length,
    flagged_param_count: result.outlier_count
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && node --test app/utils/deviceDrill.test.ts`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/deviceDrill.ts front-dev-home/app/utils/deviceDrill.test.ts
git commit -m "feat(device-statistics): shared DrillDevice view-model + outlier adapter (D22)"
```

---

## Task 2: `DrillSlideover.vue` shared component

Renders a `DrillDevice`: recipes as rows (flagged ones highlighted), each expandable to its parameters with **OTHER (기타) params listed** and flagged ones emphasized. A `highlightLabel` prop names the flag column so Plan 3 can relabel it ("위반" vs "초과").

**Files:**
- Create: `front-dev-home/app/components/ebeam/devstat/DrillSlideover.vue`

- [ ] **Step 1: Write the component**

```vue
<template>
  <USlideover
    :open="open"
    :title="device?.lot_cd ?? ''"
    :description="device?.ctn_desc || ''"
    :ui="{ content: 'w-[80vw] sm:max-w-[80vw]' }"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <template #body>
      <div class="space-y-2">
        <div class="flex flex-wrap items-center gap-3 text-[12px] text-(--sk-ink-muted)">
          <span>recipe {{ device?.recipes.length ?? 0 }}개</span>
          <span class="inline-flex items-center gap-1.5">
            <span class="inline-block h-2 w-2 rounded-full bg-rose-500" />
            {{ highlightLabel }} recipe {{ device?.flagged_recipe_count ?? 0 }}개 · 파라미터 {{ device?.flagged_param_count ?? 0 }}개
          </span>
        </div>

        <div
          v-for="recipe in device?.recipes ?? []"
          :key="recipe.recipe_id"
          class="rounded-xl ring-1 ring-(--sk-border)"
          :class="recipe.flagged ? 'bg-rose-50/60 dark:bg-rose-950/20' : 'bg-(--sk-surface)'"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
            @click="toggle(recipe.recipe_id)"
          >
            <span class="flex items-center gap-2 font-mono text-[12px] text-(--sk-ink)">
              <UIcon
                :name="expanded.has(recipe.recipe_id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
              />
              {{ recipe.recipe_id }}
            </span>
            <span class="flex items-center gap-3 text-[11px] tabular-nums text-(--sk-ink-muted)">
              <span>{{ recipe.total_params }} params</span>
              <span
                v-if="recipe.flagged_count > 0"
                class="inline-flex h-5 items-center rounded bg-rose-100 px-1.5 font-semibold text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
              >{{ highlightLabel }} {{ recipe.flagged_count }}</span>
            </span>
          </button>

          <table
            v-if="expanded.has(recipe.recipe_id)"
            class="w-full border-t border-(--sk-border) text-[12px]"
          >
            <tbody>
              <tr
                v-for="param in recipe.parameters"
                :key="param.name"
                :class="param.flagged ? 'bg-rose-100/50 dark:bg-rose-950/30' : ''"
              >
                <td class="px-3 py-1 font-mono text-(--sk-ink)">
                  {{ param.name }}
                </td>
                <td class="px-3 py-1 text-right font-mono tabular-nums text-(--sk-ink)">
                  {{ param.point_count }}
                </td>
                <td class="px-3 py-1 text-right font-mono text-[11px] text-(--sk-ink-subtle)">
                  {{ param.note ?? '' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { DrillDevice } from '~/utils/deviceDrill'

// Dumb drill-down: renders a pre-computed DrillDevice. The page decides what
// "flagged" means (outlier vs cap-violation) and passes the label (D22).
const props = defineProps<{
  open: boolean
  device: DrillDevice | null
  highlightLabel?: string
}>()

const emit = defineEmits<{ 'update:open': [boolean] }>()

const highlightLabel = computed(() => props.highlightLabel ?? '초과')
const expanded = ref<Set<string>>(new Set())

const toggle = (recipeId: string) => {
  const next = new Set(expanded.value)
  if (next.has(recipeId)) next.delete(recipeId)
  else next.add(recipeId)
  expanded.value = next
}

// Collapse all when the slideover is reopened for a different device.
watch(() => props.device?.lot_cd, () => { expanded.value = new Set() })
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS. (`DrillDevice` resolves from `~/utils/deviceDrill`; NuxtUI `USlideover`/`UIcon` are auto-imported.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/devstat/DrillSlideover.vue
git commit -m "feat(device-statistics): shared device drill-down slideover (D22)"
```

---

## Task 3: `profile.vue` — selected-set outlier table + drill

**Files:**
- Create: `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/profile.vue`

- [ ] **Step 1: Write the page** (mirrors `comparison.vue` header/empty-state + `Matrix.vue` table style)

```vue
<template>
  <div class="space-y-3">
    <EbeamFeatureHeader
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
    >
      <template #actions>
        <UButton
          size="md"
          color="neutral"
          variant="subtle"
          icon="i-lucide-arrow-left"
          :label="text.back"
          @click="goBack"
        />
      </template>
    </EbeamFeatureHeader>

    <div
      v-if="selectedLots.length === 0"
      class="dashboard-surface flex flex-col items-center justify-center rounded-2xl px-6 py-16 text-center"
    >
      <div class="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-(--sk-surface) text-(--sk-ink-subtle) ring-1 ring-(--sk-border)">
        <UIcon name="i-lucide-inbox" class="h-5 w-5" />
      </div>
      <p class="text-sm font-medium text-(--sk-ink)">
        {{ text.emptyTitle }}
      </p>
      <p class="mt-1 text-xs text-(--sk-ink-muted)">
        {{ text.emptyDesc }}
      </p>
      <UButton class="mt-4" size="sm" :label="text.emptyCta" trailing-icon="i-lucide-arrow-right" @click="goBack" />
    </div>

    <div v-else class="dashboard-surface rounded-2xl p-4">
      <p class="mb-3 text-[11.5px] text-(--sk-ink-muted)">
        {{ text.legend }}
      </p>

      <div v-if="pending" class="flex items-center justify-center gap-2 py-16 text-sm text-(--sk-ink-muted)">
        <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
        {{ text.loading }}
      </div>
      <div v-else-if="error" class="py-16 text-center text-sm text-rose-600 dark:text-rose-300">
        {{ text.loadError }}
      </div>
      <table v-else class="w-full border-collapse">
        <thead>
          <tr class="border-b border-(--sk-border)">
            <th class="px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
              디바이스
            </th>
            <th
              v-for="col in COLS"
              :key="col.key"
              class="px-2 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)"
            >
              {{ col.label }}
            </th>
            <th class="px-2 py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="dev in deviceRows"
            :key="dev.lot_cd"
            class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40"
          >
            <td class="px-3 py-1.5 font-mono text-[12.5px] text-(--sk-ink)">
              {{ dev.lot_cd }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink)">
              {{ dev.recipe_count }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink)">
              {{ dev.param_count }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink-muted)">
              {{ dev.median }}
            </td>
            <td class="px-2 py-1.5 text-right">
              <span
                class="inline-flex h-5 min-w-7 items-center justify-center rounded px-1.5 font-mono text-[11px] font-semibold tabular-nums"
                :class="dev.outlier_count > 0
                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                  : 'bg-(--sk-surface) text-(--sk-ink-subtle)'"
              >{{ dev.outlier_count }}</span>
            </td>
            <td class="px-2 py-1.5 text-right">
              <UButton size="xs" color="neutral" variant="outline" :label="text.details" @click="openDrill(dev.lot_cd)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <EbeamDevstatDrillSlideover
      v-model:open="drillOpen"
      :device="activeDrill"
      highlight-label="초과"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeInput } from '~/utils/ruleEngine'
import { detectDeviceOutliers } from '~/utils/outlierDetect'
import { toOutlierDrill, type DrillDevice } from '~/utils/deviceDrill'

definePageMeta({ hideFabSidebar: true })

const { setToolType } = useNavigation()
const { fetchRecipeParams } = useDeviceStatisticsApi()
const { selectedDeviceLots } = useDeviceCart()

const selectedLots = computed(() => selectedDeviceLots.value)

const COLS = [
  { key: 'recipes', label: 'recipe' },
  { key: 'params', label: '파라미터' },
  { key: 'median', label: '중앙값' },
  { key: 'outliers', label: 'outlier' }
] as const

const text = {
  title: '측정 프로파일',
  subtitle: '선택한 디바이스의 측정 point 분포를 비교해 과다 측정 디바이스를 확인합니다.',
  back: '뒤로',
  legend: '행 = 디바이스 · outlier = device 내 point 수가 중앙값×2 를 넘는 파라미터 개수. "자세히"로 recipe·파라미터까지 펼칩니다.',
  details: '자세히',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  emptyTitle: '선택된 디바이스가 없습니다',
  emptyDesc: '디바이스 통계에서 디바이스를 선택해 주세요.',
  emptyCta: '디바이스 선택으로'
} as const

const { data, pending, error } = await useAsyncData<RecipeInput[]>(
  'device-profile',
  () => selectedLots.value.length ? fetchRecipeParams(selectedLots.value) : Promise.resolve([]),
  { watch: [selectedLots] }
)

// Group flat recipe rows by device (lot_cd), preserving cart order.
const recipesByLot = computed(() => {
  const map = new Map<string, RecipeInput[]>()
  for (const r of data.value ?? []) {
    const bucket = map.get(r.lot_cd)
    if (bucket) bucket.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
})

interface DeviceRow {
  lot_cd: string
  recipe_count: number
  param_count: number
  median: number
  outlier_count: number
}

const deviceRows = computed<DeviceRow[]>(() => {
  const rows: DeviceRow[] = []
  for (const lot_cd of selectedLots.value) {
    const recipes = recipesByLot.value.get(lot_cd) ?? []
    const o = detectDeviceOutliers(recipes)
    rows.push({
      lot_cd,
      recipe_count: recipes.length,
      param_count: recipes.reduce((sum, r) => sum + r.parameters.length, 0),
      median: o.median,
      outlier_count: o.outlier_count
    })
  }
  // Worst (most outliers) first so over-measuring devices surface at the top.
  return rows.sort((a, b) => b.outlier_count - a.outlier_count)
})

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const ctn = recipes[0]?.ctn_desc ?? ''
  activeDrill.value = toOutlierDrill(lot_cd, ctn, recipes, detectDeviceOutliers(recipes))
  drillOpen.value = true
}

const goBack = () => navigateTo('/ebeam/cd-sem/device-statistics')

onMounted(() => setToolType('cd-sem'))
</script>
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/pages/ebeam/cd-sem/device-statistics/profile.vue
git commit -m "feat(device-statistics): selected-set measurement-profile (outlier) page (D22)"
```

---

## Task 4: Cart entry point → profile page

Add a second proceed action to the cart so a selected set can be sent to the profile page (the existing CTA still goes to `comparison.vue`).

**Files:**
- Modify: `front-dev-home/app/components/ebeam/CompareCart.vue`
- Modify: `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/index.vue`

- [ ] **Step 1: Add a `profile` emit + button in `CompareCart.vue`**

Extend the emit type (currently `proceed` + `applyPreset`, line 230-233):

```ts
const emit = defineEmits<{
  proceed: []
  profile: []
  applyPreset: [preset: DevicePreset]
}>()
```

Add a label to the `text` object:

```ts
  analyzeProfile: '측정 프로파일 비교',
```

Add a button in the selection footer, directly after the existing primary CTA `UButton` (after line 111, before the "Preset으로 저장" button):

```vue
          <UButton
            block
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-bar-chart-3"
            :disabled="selectedDeviceLots.length === 0"
            class="disabled:opacity-50"
            @click="emit('profile')"
          >
            {{ text.analyzeProfile }}
          </UButton>
```

- [ ] **Step 2: Handle `profile` in `index.vue`**

In `index.vue`, the cart is rendered at line 294 (`<EbeamCompareCart ... @proceed="proceedToStatistics" @apply-preset="applyPreset" />`). Add the handler binding:

```vue
        <EbeamCompareCart
          :selected-device-rows="selectedDeviceRows"
          :fab="selectedFab"
          @proceed="proceedToStatistics"
          @profile="proceedToProfile"
          @apply-preset="applyPreset"
        />
```

Add the handler next to `proceedToStatistics` (after line 677):

```ts
const proceedToProfile = async () => {
  if (selectedDeviceLots.value.length === 0) return
  await navigateTo('/ebeam/cd-sem/device-statistics/profile')
}
```

- [ ] **Step 3: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/CompareCart.vue front-dev-home/app/pages/ebeam/cd-sem/device-statistics/index.vue
git commit -m "feat(device-statistics): cart -> measurement-profile entry point (D22)"
```

---

## Task 5: Full verification

- [ ] **Step 1: Run typecheck + tests**

Run: `cd front-dev-home && npm run typecheck && npm run test`
Expected: PASS — `deviceDrill.test.ts`, `outlierDetect.test.ts`, `ruleEngine.test.ts` all green.

- [ ] **Step 2: Manual smoke (user runs Nuxt :3000 + Flask :5050)**

Navigate to device-statistics → select 2–3 R3 devices → "측정 프로파일 비교". Expect: a device table sorted by outlier count; clicking "자세히" opens the slideover with recipes; expanding a recipe lists its parameters with outliers highlighted in rose and a `> N` note. Verify 기타(OTHER) params appear in the parameter list.

- [ ] **Step 3: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: PASS (or auto-fixable). Fix any reported issues and re-commit.

---

## Self-Review

- **Spec coverage:** descriptive view for all fabs → `profile.vue` (Task 3) works on any selected lots regardless of fab. Within-device point-count outlier → `detectDeviceOutliers` (Plan 1) + `toOutlierDrill` (Task 1). Shared `device→recipe→parameter` drill with 기타 expanded → `DrillSlideover` (Task 2) lists every parameter incl. OTHER. Device-row unit = outlier param count → `DeviceRow.outlier_count` (Task 3). Comparable across devices → sorted device table (Task 3).
- **Type consistency:** `toOutlierDrill` returns `DrillDevice`; `DrillSlideover` consumes `DrillDevice`; `profile.vue` builds it via `toOutlierDrill`. `fetchRecipeParams` returns `RecipeInput[]`, consumed by `detectDeviceOutliers`/`toOutlierDrill`. Cart emit `profile` matches the `@profile` binding.
- **UI consistency:** header/empty-state copied from `comparison.vue`; table style from `Matrix.vue`; slideover from `RecipeDetailSlideover.vue`; `--sk-*` tokens throughout (no raw zinc for muted text).
- **No placeholders:** every step has runnable code + commands + expected output.

---

## Execution Handoff

Implement with **superpowers:subagent-driven-development** (fresh subagent per task, review between) or **superpowers:executing-plans** (inline with checkpoints). Plan 3 depends on Tasks 1–2 here (the `DrillDevice` shape + slideover).
