<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type { RecipeSearchResponse, RecipeSearchRow, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const MIN_SEARCH_LENGTH = 3
const DEFAULT_PAGE_SIZE = '50'

const { fetchRecipeList } = useRecipeSearchApi()

const query = ref('')
const pageSize = ref(DEFAULT_PAGE_SIZE)
const currentPage = ref(1)

const cacheKey = computed(() => `recipe-search:${props.toolType}:${props.fab || 'ALL'}`)

const emptyResponse = (): RecipeSearchResponse => ({
  tool_type: props.toolType,
  fab_name: props.fab || null,
  total: 0,
  rows: []
})

const { data, pending, error, refresh } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeList({ toolType: props.toolType, fabName: props.fab }),
  {
    watch: [cacheKey],
    default: emptyResponse,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const rows = computed(() => data.value?.rows ?? [])
const totalRows = computed(() => data.value?.total ?? rows.value.length)
const normalizedQuery = computed(() => query.value.trim().toLowerCase())
const canSearch = computed(() => normalizedQuery.value.length >= MIN_SEARCH_LENGTH)

const quickSearches = [
  'ABC',
  '123',
  'ABC123',
  'RACE/DEAE',
  'EA/ERJERI'
]

type SearchableRecipe = {
  row: RecipeSearchRow
  searchText: string
}

const searchableRows = computed<SearchableRecipe[]>(() => {
  return rows.value.map(row => ({
    row,
    searchText: [
      row.recipe_name,
      row.recipe_id,
      row.class_name,
      row.eqp_model_cd,
      row.fab_name
    ].join(' ').toLowerCase()
  }))
})

const filteredRows = computed(() => {
  if (!canSearch.value) return []

  const term = normalizedQuery.value
  const matches: RecipeSearchRow[] = []

  for (const item of searchableRows.value) {
    if (item.searchText.includes(term)) {
      matches.push(item.row)
    }
  }

  return matches
})

const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const filteredCount = computed(() => filteredRows.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredCount.value / pageSizeNumber.value)))
const pageStart = computed(() => filteredCount.value === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1)
const pageEnd = computed(() => Math.min(currentPage.value * pageSizeNumber.value, filteredCount.value))

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSizeNumber.value
  return filteredRows.value.slice(start, start + pageSizeNumber.value)
})

const pageSizeOptions = [
  { label: '25 / page', value: '25' },
  { label: '50 / page', value: '50' },
  { label: '100 / page', value: '100' }
]

const searchHelp = computed(() => {
  if (!query.value.trim()) {
    return 'Recipe 이름을 3자 이상 입력하면 검색이 시작됩니다.'
  }

  if (!canSearch.value) {
    return `${MIN_SEARCH_LENGTH}자 이상 입력하면 검색합니다.`
  }

  return `${filteredCount.value.toLocaleString()}개 검색됨`
})

const setQuickSearch = (value: string) => {
  query.value = value
}

const clearSearch = () => {
  query.value = ''
}

const formatUpdatedAt = (iso: string) => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso

  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

watch([normalizedQuery, pageSize, cacheKey], () => {
  currentPage.value = 1
})

watch(pageCount, (next) => {
  if (currentPage.value > next) {
    currentPage.value = next
  }

  if (currentPage.value < 1) {
    currentPage.value = 1
  }
})

const columns: TableColumn<RecipeSearchRow>[] = [
  { accessorKey: 'recipe_name', header: 'recipe_name', size: 320 },
  { accessorKey: 'recipe_id', header: 'recipe_id', size: 190 },
  { accessorKey: 'class_name', header: 'class', size: 80 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 110 },
  { accessorKey: 'updated_at', header: 'updated_at', size: 150 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis',
  th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {{ toolLabel }}
        </p>
        <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          Recipe 검색 - {{ fab }}
        </h1>
        <p class="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
          Flask에서 받은 {{ totalRows.toLocaleString() }}개 recipe 이름을 검색합니다.
        </p>
      </div>

      <div class="dashboard-surface flex overflow-hidden rounded-2xl self-start md:self-auto">
        <div class="flex min-w-[112px] flex-col gap-0.5 px-5 py-2.5">
          <span class="text-[22px] font-bold leading-none tabular-nums text-zinc-900 dark:text-zinc-100">
            {{ totalRows.toLocaleString() }}
          </span>
          <span class="text-[11px] text-zinc-500">Loaded</span>
        </div>
        <div class="flex min-w-[112px] flex-col gap-0.5 border-l border-zinc-200/70 px-5 py-2.5 dark:border-zinc-800/70">
          <span class="text-[22px] font-bold leading-none tabular-nums text-(--sk-accent)">
            {{ filteredCount.toLocaleString() }}
          </span>
          <span class="text-[11px] text-zinc-500">Matched</span>
        </div>
      </div>
    </div>

    <section class="dashboard-surface rounded-2xl px-4 py-3">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
        <UInput
          v-model="query"
          class="min-w-[16rem] flex-1"
          size="lg"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          type="search"
          autocomplete="off"
          placeholder="Recipe 이름 검색 (예: ABC, 123, RACE/DEAE)"
        />

        <div class="flex flex-wrap items-center gap-2">
          <UButton
            v-if="query"
            size="sm"
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            label="Clear"
            @click="clearSearch"
          />
          <UButton
            v-for="item in quickSearches"
            :key="item"
            size="sm"
            color="neutral"
            variant="soft"
            @click="setQuickSearch(item)"
          >
            {{ item }}
          </UButton>
        </div>
      </div>

      <div class="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span>{{ searchHelp }}</span>
        <span
          v-if="canSearch && filteredCount > 0"
          class="tabular-nums"
        >
          {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} / {{ filteredCount.toLocaleString() }}
        </span>
      </div>
    </section>

    <div
      v-if="pending"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        Recipe 목록을 불러오는 중입니다.
      </p>
    </div>

    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 text-sm font-medium text-rose-600 dark:text-rose-300">
        Recipe 목록을 불러오지 못했습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        label="Retry"
        @click="refresh()"
      />
    </div>

    <div
      v-else-if="!canSearch"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-keyboard"
        class="mx-auto h-6 w-6 text-zinc-400"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        3자 이상 입력해주세요
      </p>
      <p class="mt-1 text-xs text-zinc-500">
        Recipe 이름에는 "/"가 포함될 수 있으며, ABC 또는 123으로 바로 확인할 수 있습니다.
      </p>
    </div>

    <div
      v-else-if="filteredCount === 0"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-search-x"
        class="mx-auto h-6 w-6 text-zinc-400"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        검색 결과가 없습니다.
      </p>
      <p class="mt-1 text-xs text-zinc-500">
        다른 recipe 이름 조각을 입력해주세요.
      </p>
    </div>

    <section
      v-else
      class="dashboard-surface rounded-2xl px-3.5 py-3"
    >
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            Recipe results
          </h2>
          <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {{ filteredCount.toLocaleString() }}
          </span>
        </div>

        <USelect
          v-model="pageSize"
          class="w-[7rem]"
          size="xs"
          :items="pageSizeOptions"
        />
      </div>

      <UTable
        class="font-mono-ids"
        :columns="columns"
        :data="pagedRows"
        sticky="header"
        :ui="tableUi"
      >
        <template #recipe_name-cell="{ row }">
          <span class="font-mono text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ row.original.recipe_name }}
          </span>
        </template>

        <template #recipe_id-cell="{ row }">
          <span class="font-mono text-[12px] text-zinc-500">
            {{ row.original.recipe_id }}
          </span>
        </template>

        <template #class_name-cell="{ row }">
          <UBadge
            :label="row.original.class_name"
            color="neutral"
            size="xs"
            variant="soft"
          />
        </template>

        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12px] text-zinc-600 dark:text-zinc-300">
            {{ row.original.eqp_model_cd }}
          </span>
        </template>

        <template #updated_at-cell="{ row }">
          <span class="font-mono text-[12px] tabular-nums text-zinc-500">
            {{ formatUpdatedAt(row.original.updated_at) }}
          </span>
        </template>
      </UTable>

      <div class="mt-2 flex items-center justify-between text-xs text-zinc-500">
        <span class="tabular-nums">
          Page {{ currentPage }} / {{ pageCount }}
          <span class="ml-2 text-zinc-400">
            {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ filteredCount.toLocaleString() }}
          </span>
        </span>
        <div class="flex gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            trailing-icon="i-lucide-chevron-right"
            :disabled="currentPage >= pageCount"
            @click="currentPage += 1"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
