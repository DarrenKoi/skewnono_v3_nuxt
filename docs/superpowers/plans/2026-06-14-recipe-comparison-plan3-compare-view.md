# Recipe Comparison — Plan 3: Compare View

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the compare page — recipe set bar, parameter selection layer, and the comparison output with a 나란히 (matrix) ⇄ 분포 (grouping) toggle, parameter tabs, slot tabs, "차이만 보기", image thumbnails, and client-side Excel export.

**Architecture:** Thin `compare.vue` page wrappers (per tool) render a shared `RecipeCompareView`, mirroring how `open.vue` wraps `RecipeOpenView`. The view reads the working set from `useRecipeSelectionSet`, fetches the batch payload via `useRecipeCompareApi` + `useAsyncData`, derives overlap via the tested `utils/recipeCompare.ts`, and owns the cross-cutting controls (active parameter tab, active slot, view mode, diff-only). `ParameterSelector`, `CompareMatrix`, and `CompareGrouping` are focused children. Excel is a dynamic `xlsx` import driven by the pure `buildCompareWorkbook`.

**Tech Stack:** Nuxt 4, NuxtUI (`UCheckbox`/`UButton`/`SkNavPill`), `xlsx` (SheetJS), reuse of `recipeOpen/ImgThumb` + `recipeOpen/ImageLightbox`.

**Vue file convention:** `<template>` first, then `<script setup>` (matches `RecipeOpenView.vue` and the user's global preference).

---

## Key decisions (confirm before coding)

- The view reads recipes from `useRecipeSelectionSet(toolType, fab)` — no recipe names in the URL.
- `selectedParameters` defaults to the **common** parameters when data loads; the user can change the selection. `activeParam` is the first selected; `activeSlot` defaults to `img_meas1`.
- View mode defaults to `grouping` when `recipes.length > GROUPING_DEFAULT_THRESHOLD` (8), else `matrix`; user can toggle.
- All comparison math comes from `utils/recipeCompare.ts` (Plan 1). Components only render.

---

### Task 1: Install `xlsx` + download helper

**Files:**
- Modify: `front-dev-home/package.json` (via npm)
- Modify: `front-dev-home/app/utils/recipeCompare.ts`

- [ ] **Step 1: Install the dependency (npm, per project policy)**

Run: `cd front-dev-home && npm i xlsx`
Expected: `xlsx` added to `dependencies`.

- [ ] **Step 2: Add the browser-only download helper**

Append to `recipeCompare.ts`. It is intentionally NOT unit-tested (it touches the library + DOM); the workbook *shape* is already tested via `buildCompareWorkbook`.

```typescript
export async function downloadCompareWorkbook(
  workbook: CompareWorkbook,
  filename: string
): Promise<void> {
  const XLSX = await import('xlsx')
  const book = XLSX.utils.book_new()
  for (const sheet of workbook.sheets) {
    const ws = XLSX.utils.aoa_to_sheet(sheet.rows)
    XLSX.utils.book_append_sheet(book, ws, sheet.name.slice(0, 31))
  }
  XLSX.writeFile(book, filename)
}
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/package.json front-dev-home/package-lock.json front-dev-home/app/utils/recipeCompare.ts
git commit -m "feat(recipe-compare): add xlsx + downloadCompareWorkbook helper"
```

---

### Task 2: `ParameterSelector` component

**Files:**
- Create: `front-dev-home/app/components/ebeam/recipeCompare/ParameterSelector.vue`

Auto-imports as `<EbeamRecipeCompareParameterSelector>`.

- [ ] **Step 1: Write the component**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <div class="flex h-8 items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 dark:border-zinc-800 dark:bg-zinc-950">
        <UIcon name="i-lucide-search" class="h-3.5 w-3.5 shrink-0 text-zinc-400" />
        <input
          v-model="paramSearch"
          type="search"
          autocomplete="off"
          placeholder="파라미터 검색 (예: WAFER)"
          aria-label="파라미터 검색"
          class="w-44 min-w-0 bg-transparent text-xs text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50"
        >
      </div>
      <div class="flex items-center gap-1">
        <SkNavPill
          v-for="opt in filterOptions"
          :key="opt.value"
          size="sm"
          :label="`${opt.label} ${opt.count}`"
          :active="coverageFilter === opt.value"
          @click="coverageFilter = opt.value"
        />
      </div>
      <UButton
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-check-check"
        label="공통 전체 선택"
        @click="selectCommon"
      />
      <span class="ml-auto text-[11px] text-(--sk-ink-muted)">{{ modelValue.length }}개 선택</span>
    </div>

    <div class="max-h-[300px] overflow-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr class="sticky top-0 z-10 bg-zinc-50/90 text-left text-zinc-500 dark:bg-zinc-900/70 dark:text-zinc-400">
            <th class="w-8 p-2" />
            <th class="px-2.5 py-2 font-medium tracking-wide">parameter</th>
            <th class="px-2.5 py-2 font-medium tracking-wide">coverage</th>
            <th
              v-for="id in recipeIds"
              :key="id"
              class="px-2 py-2 text-center font-medium"
              :title="id"
            >
              {{ shortId(id) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in filteredRows"
            :key="row.parameter"
            class="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
          >
            <td class="p-2">
              <UCheckbox
                :model-value="modelValue.includes(row.parameter)"
                :aria-label="`${row.parameter} 비교 선택`"
                @update:model-value="toggleParam(row.parameter)"
              />
            </td>
            <td class="px-2.5 py-1.5 font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.parameter }}
            </td>
            <td class="px-2.5 py-1.5">
              <span class="rounded px-1.5 py-0.5 text-[9px] font-bold" :class="coverageClass(row.coverage)">
                {{ coverageLabel(row) }}
              </span>
            </td>
            <td
              v-for="id in recipeIds"
              :key="id"
              class="px-2 py-1.5 text-center"
              :class="row.presentIn.includes(id) ? 'text-emerald-500' : 'text-zinc-300 dark:text-zinc-600'"
            >
              {{ row.presentIn.includes(id) ? '✓' : '—' }}
            </td>
          </tr>
          <tr v-if="filteredRows.length === 0">
            <td :colspan="3 + recipeIds.length" class="px-3 py-6 text-center text-(--sk-ink-muted)">
              일치하는 파라미터가 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  type Coverage,
  type CoverageFilter,
  type OverlapRow,
  commonParameters,
  filterOverlap
} from '~/utils/recipeCompare'

const props = defineProps<{
  rows: OverlapRow[]
  recipeIds: string[]
}>()

const modelValue = defineModel<string[]>({ required: true })

const paramSearch = ref('')
const coverageFilter = ref<CoverageFilter>('all')

const filterOptions = computed<{ value: CoverageFilter, label: string, count: number }[]>(() => [
  { value: 'all', label: '전체', count: props.rows.length },
  { value: 'common', label: '공통', count: props.rows.filter(r => r.coverage === 'all').length },
  { value: 'partial', label: '부분', count: props.rows.filter(r => r.coverage === 'partial').length },
  { value: 'unique', label: '고유', count: props.rows.filter(r => r.coverage === 'unique').length }
])

const filteredRows = computed(() => {
  const byCoverage = filterOverlap(props.rows, coverageFilter.value)
  const term = paramSearch.value.trim().toLowerCase()
  if (!term) return byCoverage
  return byCoverage.filter(r => r.parameter.toLowerCase().includes(term))
})

const toggleParam = (parameter: string) => {
  modelValue.value = modelValue.value.includes(parameter)
    ? modelValue.value.filter(p => p !== parameter)
    : [...modelValue.value, parameter]
}

const selectCommon = () => {
  const common = commonParameters(props.rows)
  const merged = new Set([...modelValue.value, ...common])
  modelValue.value = [...merged]
}

const shortId = (id: string) => (id.length > 12 ? `…${id.slice(-10)}` : id)

const coverageLabel = (row: OverlapRow) =>
  row.coverage === 'all' ? 'ALL' : `${row.count}/${row.total}`

const coverageClass = (coverage: Coverage) =>
  coverage === 'all'
    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
    : coverage === 'partial'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-zinc-500/15 text-zinc-500'
</script>
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/app/components/ebeam/recipeCompare/ParameterSelector.vue
git commit -m "feat(recipe-compare): ParameterSelector overlap + coverage filter"
```

---

### Task 3: `CompareMatrix` component (나란히)

**Files:**
- Create: `front-dev-home/app/components/ebeam/recipeCompare/CompareMatrix.vue`

Auto-imports as `<EbeamRecipeCompareCompareMatrix>`. Reuses `recipeOpen/ImgThumb` + `recipeOpen/ImageLightbox`.

- [ ] **Step 1: Write the component**

```vue
<template>
  <div class="flex min-h-0 flex-col gap-3">
    <!-- IDP block -->
    <div class="overflow-x-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <caption class="px-2.5 py-1.5 text-left text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
          IDP · 파라미터 단위
        </caption>
        <tbody>
          <tr v-for="row in visibleIdpRows" :key="row.key" :class="row.differs ? 'bg-amber-400/10' : ''">
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-1.5 font-medium text-(--sk-ink-muted)">{{ row.label }}</td>
            <td
              v-for="(value, i) in row.values"
              :key="i"
              class="px-2.5 py-1.5 text-zinc-900 dark:text-zinc-100"
              :class="row.differs ? 'font-bold' : ''"
            >{{ value }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- AMP block for active slot -->
    <div class="overflow-x-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr class="bg-zinc-50/80 text-left dark:bg-zinc-900/60">
            <th class="sticky left-0 z-10 bg-inherit px-2.5 py-2 font-medium text-(--sk-ink-muted)">{{ slotLabel }}</th>
            <th v-for="id in recipeIds" :key="id" class="px-2.5 py-2 text-left font-medium" :title="id">{{ shortId(id) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-2 text-(--sk-ink-muted)">이미지</td>
            <td v-for="(file, i) in images" :key="i" class="px-2 py-2 align-top">
              <EbeamRecipeOpenImgThumb
                v-if="file"
                :image-slot="slotDescriptor"
                :filename="file"
                @open="openLightbox(i, file)"
              />
              <span v-else class="text-rose-500">없음</span>
            </td>
          </tr>
          <tr v-for="row in visibleAmpRows" :key="row.key" :class="row.differs ? 'bg-amber-400/10' : ''">
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-1.5 font-medium text-(--sk-ink-muted)">
              {{ row.label }}<span v-if="row.unit" class="ml-1 text-zinc-400">({{ row.unit }})</span>
            </td>
            <td
              v-for="(value, i) in row.values"
              :key="i"
              class="px-2.5 py-1.5 text-zinc-900 dark:text-zinc-100"
              :class="row.differs ? 'font-bold' : ''"
            >{{ value }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <EbeamRecipeOpenImageLightbox v-model:open="lightboxOpen" :data="lightboxData" />
  </div>
</template>

<script setup lang="ts">
import type { CompareRecipe } from '~/composables/useRecipeCompareApi'
import { buildAmpRows, buildIdpRows, imageFilenames, findParameter } from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
import type { LightboxData } from '~/components/ebeam/recipeOpen/ImageLightbox.vue'

const props = defineProps<{
  recipes: CompareRecipe[]
  parameter: string
  slotKey: ImageSlotKey
  diffOnly: boolean
}>()

const recipeIds = computed(() => props.recipes.map(r => r.recipe_id))
const slotDescriptor = computed(() => IMAGE_SLOTS.find(s => s.key === props.slotKey) ?? IMAGE_SLOTS[0]!)
const slotLabel = computed(() => slotDescriptor.value.stage)

const idpRows = computed(() => buildIdpRows(props.recipes, props.parameter))
const ampRows = computed(() => buildAmpRows(props.recipes, props.parameter, props.slotKey))
const images = computed(() => imageFilenames(props.recipes, props.parameter, props.slotKey))

const visibleIdpRows = computed(() => props.diffOnly ? idpRows.value.filter(r => r.differs) : idpRows.value)
const visibleAmpRows = computed(() => props.diffOnly ? ampRows.value.filter(r => r.differs) : ampRows.value)

const shortId = (id: string) => (id.length > 12 ? `…${id.slice(-10)}` : id)

const lightboxOpen = ref(false)
const lightboxData = ref<LightboxData | null>(null)

const openLightbox = (recipeIndex: number, filename: string) => {
  const recipe = props.recipes[recipeIndex]
  const param = recipe ? findParameter(recipe, props.parameter) : null
  const ampRow = param?.amp.find(a => a.slot === props.slotKey) ?? null
  lightboxData.value = { slot: slotDescriptor.value, filename, ampRow }
  lightboxOpen.value = true
}
</script>
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/app/components/ebeam/recipeCompare/CompareMatrix.vue
git commit -m "feat(recipe-compare): CompareMatrix side-by-side view"
```

---

### Task 4: `CompareGrouping` component (분포)

**Files:**
- Create: `front-dev-home/app/components/ebeam/recipeCompare/CompareGrouping.vue`

Auto-imports as `<EbeamRecipeCompareCompareGrouping>`.

- [ ] **Step 1: Write the component**

```vue
<template>
  <div class="flex flex-col gap-1.5">
    <div
      v-for="field in fields"
      :key="field.key"
      class="flex flex-wrap items-center gap-2 border-b border-zinc-100 py-2 dark:border-zinc-800/60"
    >
      <span class="w-28 shrink-0 font-mono text-[11px] font-medium text-(--sk-ink-muted)">{{ field.label }}</span>
      <button
        v-for="bucket in field.buckets"
        :key="bucket.value"
        type="button"
        class="rounded-md px-2.5 py-1 font-mono text-[11px] transition"
        :class="bucket.isOutlier
          ? 'bg-rose-500/15 text-rose-600 ring-1 ring-rose-500/40 dark:text-rose-300'
          : 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300'"
        @click="toggleExpand(field.key, bucket.value)"
      >
        {{ bucket.value }} ×{{ bucket.count }}<span v-if="bucket.isOutlier"> ⚠</span>
      </button>
      <div
        v-if="expanded === `${field.key}::pick`"
        class="basis-full pt-1 pl-28 font-mono text-[10px] text-(--sk-ink-muted)"
      >
        {{ expandedRecipeIds.join(', ') }}
      </div>
    </div>
    <p v-if="fields.length === 0" class="py-6 text-center text-[11px] text-(--sk-ink-muted)">
      차이가 있는 항목이 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { CompareRecipe } from '~/composables/useRecipeCompareApi'
import {
  type MatrixRow,
  type ValueBucket,
  buildAmpRows,
  buildIdpRows,
  groupFieldValues
} from '~/utils/recipeCompare'
import type { ImageSlotKey } from '~/utils/recipeView'

const props = defineProps<{
  recipes: CompareRecipe[]
  parameter: string
  slotKey: ImageSlotKey
  diffOnly: boolean
}>()

interface GroupedField {
  key: string
  label: string
  buckets: ValueBucket[]
}

const recipeIds = computed(() => props.recipes.map(r => r.recipe_id))

const groupRow = (row: MatrixRow): GroupedField => ({
  key: row.key,
  label: row.label,
  buckets: groupFieldValues(row.values.map((value, i) => ({ recipeId: recipeIds.value[i]!, value })))
})

const fields = computed<GroupedField[]>(() => {
  const rows = [
    ...buildIdpRows(props.recipes, props.parameter),
    ...buildAmpRows(props.recipes, props.parameter, props.slotKey)
  ]
  const grouped = rows.map(groupRow)
  return props.diffOnly ? grouped.filter(f => f.buckets.length > 1) : grouped
})

const expanded = ref<string | null>(null)
const expandedRecipeIds = ref<string[]>([])

const toggleExpand = (fieldKey: string, value: string) => {
  const token = `${fieldKey}::pick`
  const field = fields.value.find(f => f.key === fieldKey)
  const bucket = field?.buckets.find(b => b.value === value)
  if (expanded.value === token && expandedRecipeIds.value.join() === (bucket?.recipeIds ?? []).join()) {
    expanded.value = null
    expandedRecipeIds.value = []
    return
  }
  expanded.value = token
  expandedRecipeIds.value = bucket?.recipeIds ?? []
}
</script>
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/app/components/ebeam/recipeCompare/CompareGrouping.vue
git commit -m "feat(recipe-compare): CompareGrouping outlier/distribution view"
```

---

### Task 5: `RecipeSetBar` component

**Files:**
- Create: `front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue`

Auto-imports as `<EbeamRecipeCompareRecipeSetBar>`. Inline add type-ahead is backed by the shared recipe catalog (same cache key as the search page, so it's free).

- [ ] **Step 1: Write the component**

```vue
<template>
  <div class="dashboard-surface flex flex-col gap-3 rounded-2xl p-4 lg:flex-row lg:items-center">
    <div class="min-w-0 flex-1">
      <p class="mb-1.5 text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
        비교 대상 recipe · {{ selected.length }}
      </p>
      <div class="flex flex-wrap items-center gap-1.5">
        <span
          v-for="name in selected"
          :key="name"
          class="inline-flex max-w-[240px] items-center gap-1 rounded-full bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[10.5px] text-zinc-700 dark:text-zinc-200"
        >
          <span class="truncate">{{ name }}</span>
          <button type="button" :aria-label="`Remove ${name}`" class="rounded-full p-0.5 hover:bg-zinc-300 dark:hover:bg-zinc-600" @click="emit('remove', name)">
            <UIcon name="i-lucide-x" class="h-3 w-3" />
          </button>
        </span>

        <div class="relative">
          <input
            v-model="addQuery"
            type="search"
            autocomplete="off"
            placeholder="＋ recipe 추가…"
            aria-label="recipe 추가"
            class="w-44 rounded-full border border-dashed border-zinc-300 bg-transparent px-3 py-1 font-mono text-[10.5px] outline-none focus:border-(--sk-brand) dark:border-zinc-700"
          >
          <div
            v-if="suggestions.length"
            class="absolute z-30 mt-1 max-h-56 w-72 overflow-auto rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
          >
            <button
              v-for="name in suggestions"
              :key="name"
              type="button"
              class="block w-full truncate px-3 py-1.5 text-left font-mono text-[10.5px] hover:bg-zinc-100 dark:hover:bg-zinc-800"
              @click="pick(name)"
            >{{ name }}</button>
          </div>
        </div>
      </div>
    </div>

    <UButton
      class="shrink-0"
      size="sm"
      color="success"
      variant="soft"
      icon="i-lucide-download"
      label="Excel 다운로드"
      :disabled="!canExport"
      @click="emit('download')"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const props = defineProps<{
  selected: string[]
  toolType: RecipeSearchToolType
  fab: string
  canExport: boolean
}>()

const emit = defineEmits<{
  remove: [name: string]
  add: [name: string]
  download: []
}>()

const { fetchRecipeList } = useRecipeSearchApi()

const { data: catalog } = await useAsyncData(
  () => `recipe-search:${props.toolType}:${props.fab || 'ALL'}`,
  () => fetchRecipeList({ toolType: props.toolType, fabName: props.fab }),
  { getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key] }
)

const addQuery = ref('')

const suggestions = computed(() => {
  const term = addQuery.value.trim().toLowerCase()
  if (term.length < 3) return []
  const all = catalog.value?.rows ?? []
  const matches: string[] = []
  for (const name of all) {
    if (props.selected.includes(name)) continue
    if (name.toLowerCase().includes(term)) matches.push(name)
    if (matches.length >= 8) break
  }
  return matches
})

const pick = (name: string) => {
  emit('add', name)
  addQuery.value = ''
}
</script>
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue
git commit -m "feat(recipe-compare): RecipeSetBar with inline add + Excel button"
```

---

### Task 6: `RecipeCompareView` orchestrator

**Files:**
- Create: `front-dev-home/app/components/ebeam/RecipeCompareView.vue`

Auto-imports as `<EbeamRecipeCompareView>`.

- [ ] **Step 1: Write the view**

```vue
<template>
  <div class="mx-auto w-full max-w-[1440px] space-y-4">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe 비교"
      subtitle="선택한 recipe들의 파라미터·측정 설정을 나란히/분포로 비교합니다."
      :stats="metaStats"
    />

    <div v-if="selected.length < 2" class="dashboard-surface rounded-2xl px-6 py-12 text-center">
      <UIcon name="i-lucide-scale" class="mx-auto h-6 w-6 text-zinc-400" />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">비교하려면 recipe를 2개 이상 선택하세요.</p>
      <UButton class="mt-3" size="sm" color="neutral" variant="outline" label="Recipe 검색으로" :to="backRoute" />
    </div>

    <template v-else>
      <EbeamRecipeCompareRecipeSetBar
        :selected="selected"
        :tool-type="toolType"
        :fab="fab"
        :can-export="!!data && selectedParameters.length > 0"
        @remove="remove"
        @add="add"
        @download="downloadExcel"
      />

      <div v-if="pending" class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)">
        <UIcon name="i-lucide-loader-circle" class="mx-auto h-5 w-5 animate-spin text-zinc-400" />
        <p class="mt-2">비교 데이터를 불러오는 중입니다.</p>
      </div>

      <div v-else-if="error" class="dashboard-surface rounded-2xl px-6 py-12 text-center">
        <UIcon name="i-lucide-circle-alert" class="mx-auto h-6 w-6 text-rose-500" />
        <p class="mt-2 text-sm font-medium text-rose-600 dark:text-rose-300">비교 데이터를 불러오지 못했습니다.</p>
        <UButton class="mt-3" size="sm" color="neutral" variant="outline" icon="i-lucide-refresh-cw" label="Retry" @click="refresh()" />
      </div>

      <template v-else-if="recipes.length">
        <EbeamRecipeCompareParameterSelector
          v-model="selectedParameters"
          :rows="overlapRows"
          :recipe-ids="recipeIds"
        />

        <section v-if="selectedParameters.length" class="dashboard-surface rounded-2xl p-4">
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <div class="flex flex-wrap gap-1">
              <SkNavPill
                v-for="param in selectedParameters"
                :key="param"
                size="sm"
                :label="param"
                :active="activeParam === param"
                @click="activeParam = param"
              />
            </div>
            <div class="ml-auto flex items-center gap-2">
              <label class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)">
                <UCheckbox v-model="diffOnly" /> 차이만 보기
              </label>
              <div class="flex rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
                <button
                  type="button"
                  class="rounded-md px-3 py-1 text-[11px] font-semibold transition"
                  :class="viewMode === 'matrix' ? 'bg-white shadow-sm dark:bg-zinc-950' : 'text-(--sk-ink-muted)'"
                  @click="viewMode = 'matrix'"
                >나란히</button>
                <button
                  type="button"
                  class="rounded-md px-3 py-1 text-[11px] font-semibold transition"
                  :class="viewMode === 'grouping' ? 'bg-white shadow-sm dark:bg-zinc-950' : 'text-(--sk-ink-muted)'"
                  @click="viewMode = 'grouping'"
                >분포</button>
              </div>
            </div>
          </div>

          <div class="mb-3 flex flex-wrap gap-1.5">
            <SkNavPill
              v-for="s in IMAGE_SLOTS"
              :key="s.key"
              size="sm"
              :label="s.stage"
              :active="activeSlot === s.key"
              @click="activeSlot = s.key"
            />
          </div>

          <EbeamRecipeCompareCompareMatrix
            v-if="viewMode === 'matrix'"
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
          />
          <EbeamRecipeCompareCompareGrouping
            v-else
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
          />
        </section>

        <div v-else class="dashboard-surface rounded-2xl px-6 py-10 text-center text-sm text-(--sk-ink-muted)">
          비교할 파라미터를 선택하세요. (공통 전체 선택을 눌러보세요.)
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { RecipeCompareResponse } from '~/composables/useRecipeCompareApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import {
  GROUPING_DEFAULT_THRESHOLD,
  buildCompareWorkbook,
  buildOverlap,
  commonParameters,
  downloadCompareWorkbook
} from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const { selected, add, remove } = useRecipeSelectionSet(props.toolType, props.fab)
const { fetchCompare } = useRecipeCompareApi()

const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const cacheKey = computed(() => `recipe-compare:${props.toolType}:${props.fab || 'ALL'}:${[...selected.value].sort().join('|')}`)

const { data, pending, error, refresh } = await useAsyncData<RecipeCompareResponse | null>(
  () => cacheKey.value,
  () => {
    if (selected.value.length < 2) return Promise.resolve(null)
    return fetchCompare({ toolType: props.toolType, fabName: props.fab, recipeNames: selected.value })
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const recipes = computed(() => data.value?.recipes ?? [])
const recipeIds = computed(() => recipes.value.map(r => r.recipe_id))
const overlapRows = computed(() => buildOverlap(recipes.value))

const selectedParameters = ref<string[]>([])
const activeParam = ref('')
const activeSlot = ref<ImageSlotKey>('img_meas1')
const diffOnly = ref(false)
const viewMode = ref<'matrix' | 'grouping'>('matrix')

// When a new dataset loads, default the parameter selection to common params and
// the view mode to grouping for large sets.
watch(overlapRows, (rows) => {
  if (rows.length === 0) return
  const common = commonParameters(rows)
  selectedParameters.value = common.length ? common : [rows[0]!.parameter]
  viewMode.value = recipes.value.length > GROUPING_DEFAULT_THRESHOLD ? 'grouping' : 'matrix'
}, { immediate: true })

// Keep activeParam valid as the selection changes.
watch(selectedParameters, (params) => {
  if (!params.includes(activeParam.value)) {
    activeParam.value = params[0] ?? ''
  }
}, { immediate: true })

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'recipes', label: 'Recipes', value: selected.value.length.toLocaleString(), tone: 'accent' },
  { key: 'params', label: 'Params', value: selectedParameters.value.length.toLocaleString(), tone: 'neutral' }
])

const downloadExcel = () => {
  if (!recipes.value.length || !selectedParameters.value.length) return
  const workbook = buildCompareWorkbook(recipes.value, selectedParameters.value)
  downloadCompareWorkbook(workbook, `recipe-compare_${props.toolType}_${props.fab}.xlsx`)
}
</script>
```

- [ ] **Step 2: Typecheck + lint + commit**

```bash
cd front-dev-home && npm run typecheck && npm run lint
git add front-dev-home/app/components/ebeam/RecipeCompareView.vue
git commit -m "feat(recipe-compare): RecipeCompareView orchestrator"
```

---

### Task 7: Page wrappers

**Files:**
- Create: `front-dev-home/app/pages/ebeam/cd-sem/[fab]/recipe-search/compare.vue`
- Create: `front-dev-home/app/pages/ebeam/hv-sem/[fab]/recipe-search/compare.vue`

- [ ] **Step 1: Write the CD-SEM wrapper**

```vue
<template>
  <EbeamRecipeCompareView
    :fab="fabId"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('cd-sem')
applyFab(fabId.value)

watch(fabId, (next) => {
  applyFab(next)
})
</script>
```

- [ ] **Step 2: Write the HV-SEM wrapper**

Identical except `tool-label="HV-SEM"`, `tool-type="hv-sem"`, and `setToolType('hv-sem')`:

```vue
<template>
  <EbeamRecipeCompareView
    :fab="fabId"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('hv-sem')
applyFab(fabId.value)

watch(fabId, (next) => {
  applyFab(next)
})
</script>
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd front-dev-home && npm run typecheck
git add front-dev-home/app/pages/ebeam/cd-sem/[fab]/recipe-search/compare.vue front-dev-home/app/pages/ebeam/hv-sem/[fab]/recipe-search/compare.vue
git commit -m "feat(recipe-compare): compare page wrappers (cd-sem + hv-sem)"
```

---

### Task 8: End-to-end manual verification

- [ ] **Step 1: Exercise the full flow with Playwright MCP** (screenshots → `.playwright-mcp/screenshots/`)

With Flask (:5050) + Nuxt (:3000) running:

1. `http://localhost:3000/ebeam/cd-sem/r3/recipe-search` → search, check 3 recipes → 비교하기.
2. On `/recipe-search/compare`: confirm the set bar shows 3 chips; ParameterSelector lists parameters with `ALL`/partial tags.
3. Click "공통 전체 선택" → parameter tabs appear; matrix renders with diff highlighting and a thumbnail row.
4. Click a thumbnail → lightbox opens with that slot's AMP fields.
5. Switch slot tabs (Meas 1 → Add 1) → fields + thumbnails update.
6. Toggle "차이만 보기" → rows where all recipes agree disappear.
7. Toggle 분포 → value buckets render; an outlier bucket shows ⚠; click it → deviating recipe ids list.
8. Click "Excel 다운로드" → an `.xlsx` downloads; open it and confirm Overlap + IDP + per-slot sheets.
9. Add a recipe via the set bar's inline type-ahead → comparison re-fetches and re-renders.

- [ ] **Step 2: Verify the large-N path**

Select ~12+ recipes, open compare → confirm it defaults to 분포 view and the matrix scrolls horizontally with a sticky first column when toggled to 나란히.

- [ ] **Step 3: Record the result + final checks**

```bash
cd front-dev-home && npm run test && npm run typecheck && npm run lint
```

Expected: all green. Confirm the flow in the conversation; commit any fixes as `fix(recipe-compare): ...`.

---

## Done when

- The compare page renders overlap → parameter tabs → matrix/grouping with slot tabs, diff-only, thumbnails, and lightbox.
- 분포 view flags outliers; 나란히 view highlights differing rows; large N defaults to 분포 and scrolls.
- Excel export produces Overlap + IDP + per-slot sheets.
- `npm run test`, `npm run typecheck`, `npm run lint` all pass.
