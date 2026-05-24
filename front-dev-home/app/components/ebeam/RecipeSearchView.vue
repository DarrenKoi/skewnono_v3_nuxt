<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type { RecipeSearchResponse, RecipeSearchRow, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const MIN_SEARCH_LENGTH = 3
const DEFAULT_PAGE_SIZE = '50'

const { fetchRecipeList } = useRecipeSearchApi()
const {
  recentSearches,
  recordRecentSearch,
  removeRecentSearch,
  clearRecentSearches
} = useRecipeRecentSearches(props.toolType, props.fab)
const route = useRoute()
const router = useRouter()

const readStringQuery = (key: string) => {
  const raw = route.query[key]
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value : ''
}

const readPageQuery = () => {
  const parsed = Number.parseInt(readStringQuery('page'), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

const initialPageSize = readStringQuery('size') || DEFAULT_PAGE_SIZE

const query = ref(readStringQuery('q'))
const pageSize = ref(initialPageSize)
const currentPage = ref(readPageQuery())

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

const recipeNames = computed(() => data.value?.rows ?? [])
const rows = computed<RecipeSearchRow[]>(() => recipeNames.value.map(recipeName => ({ recipe_name: recipeName })))
const totalRows = computed(() => data.value?.total ?? recipeNames.value.length)
const normalizedQuery = computed(() => query.value.trim().toLowerCase())
const canSearch = computed(() => normalizedQuery.value.length >= MIN_SEARCH_LENGTH)

type SearchableRecipe = {
  row: RecipeSearchRow
  searchText: string
}

const searchableRows = computed<SearchableRecipe[]>(() => {
  return rows.value.map(row => ({
    row,
    searchText: row.recipe_name.toLowerCase()
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

// In-table filter: live-narrows the coarse top-bar matches (AND composition),
// so you can drill within a large result family without re-running the search.
const tableFilter = ref('')
const normalizedTableFilter = computed(() => tableFilter.value.trim().toLowerCase())
const isRefining = computed(() => normalizedTableFilter.value.length > 0)

const refinedRows = computed(() => {
  if (!isRefining.value) return filteredRows.value
  const term = normalizedTableFilter.value
  return filteredRows.value.filter(row => row.recipe_name.toLowerCase().includes(term))
})

const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const filteredCount = computed(() => filteredRows.value.length)
const refinedCount = computed(() => refinedRows.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(refinedCount.value / pageSizeNumber.value)))
const pageStart = computed(() => refinedCount.value === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1)
const pageEnd = computed(() => Math.min(currentPage.value * pageSizeNumber.value, refinedCount.value))

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSizeNumber.value
  return refinedRows.value.slice(start, start + pageSizeNumber.value)
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

// Fab/scope rides in the mono eyebrow; the <h1> stays the fixed page name so
// the header never renames itself per fab (DESIGN.md §7.8).
const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)

const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'loaded', label: 'Loaded', value: totalRows.value.toLocaleString(), tone: 'neutral' },
  { key: 'matched', label: 'Matched', value: filteredCount.value.toLocaleString(), tone: 'accent' }
])

const applyRecentSearch = (value: string) => {
  query.value = value
}

const commitSearch = () => {
  if (canSearch.value) {
    recordRecentSearch(query.value.trim())
  }
}

const clearSearch = () => {
  query.value = ''
}

watch([normalizedQuery, pageSize, cacheKey], () => {
  currentPage.value = 1
  tableFilter.value = ''
})

watch(normalizedTableFilter, () => {
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

watch([query, pageSize, currentPage], ([nextQuery, nextSize, nextPage]) => {
  const nextRouteQuery: Record<string, string> = {}

  for (const [key, value] of Object.entries(route.query)) {
    if (key === 'q' || key === 'size' || key === 'page') continue
    if (typeof value === 'string') nextRouteQuery[key] = value
  }

  if (nextQuery) nextRouteQuery.q = nextQuery
  if (nextSize && nextSize !== DEFAULT_PAGE_SIZE) nextRouteQuery.size = nextSize
  if (nextPage > 1) nextRouteQuery.page = String(nextPage)

  if ((route.query.q ?? '') === (nextRouteQuery.q ?? '')
    && (route.query.size ?? '') === (nextRouteQuery.size ?? '')
    && (route.query.page ?? '') === (nextRouteQuery.page ?? '')) {
    return
  }

  router.replace({ query: nextRouteQuery })
})

const columns: TableColumn<RecipeSearchRow>[] = [
  { accessorKey: 'recipe_name', header: 'recipe_name', size: 520 },
  { id: 'open', header: '', size: 400 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-2.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}

const recipeSubpath = (subpath: string) => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search/${subpath}`

const getRecipeDetailRoute = (recipeName: string) => ({
  path: recipeSubpath('open'),
  query: { recipe_name: recipeName }
})

const getLateralRoute = (recipeName: string) => ({
  path: recipeSubpath('lateral'),
  query: { recipe_name: recipeName }
})

const getMeasHistRoute = (recipeName: string) => ({
  path: recipeSubpath('meas-hist'),
  query: { recipe_name: recipeName }
})

const openRecipeDetail = (recipeName: string) => {
  recordRecentSearch(query.value.trim())
  router.push(getRecipeDetailRoute(recipeName))
}

const openLateral = (recipeName: string) => {
  recordRecentSearch(query.value.trim())
  router.push(getLateralRoute(recipeName))
}

const openMeasHist = (recipeName: string) => {
  recordRecentSearch(query.value.trim())
  router.push(getMeasHistRoute(recipeName))
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1440px] space-y-4">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe 검색"
      subtitle="DB에 등록된 Recipe를 빠르게 검색합니다."
      :stats="metaStats"
    />

    <div class="space-y-4">
      <section class="dashboard-surface rounded-2xl p-5">
        <form
          class="group flex h-14 w-full items-center gap-2 rounded-full border border-zinc-200 bg-white px-5 shadow-sm transition focus-within:border-zinc-300 focus-within:ring-4 focus-within:ring-zinc-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:focus-within:border-zinc-700 dark:focus-within:ring-zinc-800/70"
          @submit.prevent="commitSearch"
        >
          <UIcon
            name="i-lucide-search"
            class="h-5 w-5 shrink-0 text-zinc-400"
          />
          <input
            v-model="query"
            type="search"
            inputmode="search"
            autocomplete="off"
            class="min-w-0 flex-1 bg-transparent text-base text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50"
            aria-label="Search recipes"
            placeholder="Recipe 이름 검색 (예: ABC, 123, RACE/DEAE)"
          >
          <UButton
            v-if="query"
            type="button"
            size="sm"
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            aria-label="Clear search"
            class="rounded-full"
            @click="clearSearch"
          />
          <UButton
            type="submit"
            size="sm"
            color="neutral"
            variant="solid"
            icon="i-lucide-arrow-right"
            aria-label="Save search"
            class="rounded-full"
            :disabled="!canSearch"
          />
        </form>

        <div
          v-if="recentSearches.length"
          class="mt-2.5 flex flex-wrap items-center gap-1.5"
        >
          <span class="text-xs font-medium uppercase tracking-wide text-(--sk-ink-muted)">
            Recent
          </span>
          <div
            v-for="term in recentSearches"
            :key="term"
            class="inline-flex items-center gap-0.5 rounded-full bg-zinc-100 py-1 pl-3 pr-1.5 text-sm text-zinc-700 transition hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            <button
              type="button"
              class="font-mono leading-5"
              @click="applyRecentSearch(term)"
            >
              {{ term }}
            </button>
            <button
              type="button"
              class="rounded-full p-0.5 text-zinc-400 transition hover:bg-zinc-300 hover:text-zinc-900 dark:hover:bg-zinc-600 dark:hover:text-zinc-50"
              :aria-label="`Remove ${term} from recent searches`"
              @click.stop="removeRecentSearch(term)"
            >
              <UIcon
                name="i-lucide-x"
                class="h-3.5 w-3.5"
              />
            </button>
          </div>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            label="Clear all"
            @click="clearRecentSearches"
          />
        </div>

        <div class="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-(--sk-ink-muted)">
          <span>{{ searchHelp }}</span>
          <span
            v-if="canSearch && refinedCount > 0"
            class="tabular-nums"
          >
            {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} / {{ refinedCount.toLocaleString() }}
          </span>
        </div>
      </section>

      <div
        v-if="pending"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
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
        <p class="mt-1 text-xs text-(--sk-ink-muted)">
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
        <p class="mt-1 text-xs text-(--sk-ink-muted)">
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
              <template v-if="isRefining">{{ refinedCount.toLocaleString() }} / {{ filteredCount.toLocaleString() }}</template>
              <template v-else>{{ filteredCount.toLocaleString() }}</template>
            </span>
          </div>

          <div class="flex items-center gap-2">
            <div class="group flex h-8 items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 transition focus-within:border-zinc-300 focus-within:ring-2 focus-within:ring-zinc-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:focus-within:border-zinc-700 dark:focus-within:ring-zinc-800/70">
              <UIcon
                name="i-lucide-filter"
                class="h-3.5 w-3.5 shrink-0 text-zinc-400"
              />
              <input
                v-model="tableFilter"
                type="search"
                autocomplete="off"
                class="w-40 min-w-0 bg-transparent text-xs text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50"
                aria-label="Filter results"
                placeholder="결과 내 필터"
              >
              <button
                v-if="tableFilter"
                type="button"
                class="shrink-0 rounded-full p-0.5 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
                aria-label="Clear filter"
                @click="tableFilter = ''"
              >
                <UIcon
                  name="i-lucide-x"
                  class="h-3 w-3"
                />
              </button>
            </div>

            <USelect
              v-model="pageSize"
              class="w-[7rem]"
              size="xs"
              :items="pageSizeOptions"
            />
          </div>
        </div>

        <UTable
          class="font-mono-ids"
          :columns="columns"
          :data="pagedRows"
          sticky="header"
          :ui="tableUi"
        >
          <template #empty>
            <div class="py-8 text-center text-xs text-(--sk-ink-muted)">
              <UIcon
                name="i-lucide-filter-x"
                class="mx-auto mb-1.5 h-5 w-5 text-zinc-400"
              />
              <p>필터 "<span class="font-mono text-zinc-700 dark:text-zinc-300">{{ tableFilter }}</span>"와 일치하는 recipe가 없습니다.</p>
            </div>
          </template>

          <template #recipe_name-cell="{ row }">
            <span class="font-mono text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.original.recipe_name }}
            </span>
          </template>

          <template #open-cell="{ row }">
            <div class="flex flex-wrap items-center gap-2.5">
              <UButton
                size="sm"
                color="neutral"
                variant="outline"
                icon="i-lucide-file-search"
                label="열어 보기"
                @click="openRecipeDetail(row.original.recipe_name)"
              />
              <UButton
                size="sm"
                color="neutral"
                variant="outline"
                icon="i-lucide-network"
                label="횡전개"
                @click="openLateral(row.original.recipe_name)"
              />
              <UButton
                size="sm"
                color="neutral"
                variant="outline"
                icon="i-lucide-history"
                label="측정 이력"
                @click="openMeasHist(row.original.recipe_name)"
              />
            </div>
          </template>
        </UTable>

        <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
          <span class="tabular-nums">
            Page {{ currentPage }} / {{ pageCount }}
            <span class="ml-2 text-zinc-400">
              {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ refinedCount.toLocaleString() }}
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
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
