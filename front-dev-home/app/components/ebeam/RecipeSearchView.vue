<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type { RecipeSearchResponse, RecipeSearchRow, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { matchesRecipeQuery, matchingHistoryNames, tokenizeRecipeQuery } from '~/utils/recipeSearchMatch'

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
// `_` segments carry meaning (manufacturing tech codes), so the query is
// tokenized on whitespace/underscores and AND-composed — see recipeSearchMatch.
const queryTokens = computed(() => tokenizeRecipeQuery(query.value))

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

  const tokens = queryTokens.value
  const matches: RecipeSearchRow[] = []

  for (const item of searchableRows.value) {
    if (matchesRecipeQuery(item.searchText, tokens)) {
      matches.push(item.row)
    }
  }

  return matches
})

// In-table filter: live-narrows the coarse top-bar matches (AND composition),
// so you can drill within a large result family without re-running the search.
const tableFilter = ref('')
const tableFilterTokens = computed(() => tokenizeRecipeQuery(tableFilter.value))
const isRefining = computed(() => tableFilterTokens.value.length > 0)

const refinedRows = computed(() => {
  if (!isRefining.value) return filteredRows.value
  const tokens = tableFilterTokens.value
  return filteredRows.value.filter(row => matchesRecipeQuery(row.recipe_name.toLowerCase(), tokens))
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

watch(tableFilterTokens, () => {
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

// --- 측정 이력 fallback -----------------------------------------------------
// The redis recipe catalog refreshes daily, but the meas_hist_* indices are
// ~15 min fresh. When a 3+ char lookup matches nothing, probe measurement
// history so a just-created recipe isn't mistaken for a typo.
const HISTORY_PROBE_DEBOUNCE_MS = 600
// The endpoint pages by recency; 200 rows is plenty for an existence probe
// and stays under the backend's limit clamp (DEFAULT_LIMIT * 10).
const HISTORY_PROBE_LIMIT = 200

const { searchMeasHist } = useMeasHistApi()
const toast = useToast()

const historyMatches = ref<string[]>([])

const historyMatchesLabel = computed(() => {
  const names = historyMatches.value
  const shown = names.slice(0, 3).join(', ')
  return names.length > 3 ? `${shown} 외 ${names.length - 3}건` : shown
})

// Non-empty exactly when a settled zero-result search is on screen; doubles
// as the probe's identity so stale responses and repeat toasts can be culled.
const historyProbeKey = computed(() =>
  canSearch.value && !pending.value && !error.value && filteredCount.value === 0
    ? `${props.toolType}:${props.fab || 'ALL'}:${normalizedQuery.value}`
    : ''
)

let historyProbeTimer: ReturnType<typeof setTimeout> | undefined
let historyProbeSeq = 0
let lastHistoryToastKey = ''

watch(historyProbeKey, (key) => {
  clearTimeout(historyProbeTimer)
  const seq = ++historyProbeSeq
  historyMatches.value = []
  if (!key) return

  const tokens = queryTokens.value
  historyProbeTimer = setTimeout(async () => {
    try {
      const response = await searchMeasHist({
        toolType: props.toolType,
        fab: props.fab ? [props.fab] : undefined,
        recipe: tokens,
        limit: HISTORY_PROBE_LIMIT
      })
      if (seq !== historyProbeSeq) return

      const matches = matchingHistoryNames(response.rows.map(row => row.full_name), tokens)
      historyMatches.value = matches

      if (matches.length && lastHistoryToastKey !== key) {
        lastHistoryToastKey = key
        const first = matches[0] ?? ''
        toast.add({
          title: 'redis에는 없지만 측정 기록은 발견됩니다. (redis update 주기 1일)',
          description: matches.length === 1 ? first : `${first} 외 ${matches.length - 1}건`,
          icon: 'i-lucide-history',
          color: 'warning'
        })
      }
    } catch {
      // Best-effort hint: a failed probe just means no notice, never an error UI.
    }
  }, HISTORY_PROBE_DEBOUNCE_MS)
  // immediate: setup awaits the catalog fetch, so on a deep link (?q=...) the
  // key is already settled by the time this watcher registers — without it the
  // probe would only ever run after further typing.
}, { immediate: true })

onBeforeUnmount(() => clearTimeout(historyProbeTimer))

const columns: TableColumn<RecipeSearchRow>[] = [
  { id: 'select', header: '', size: 36 },
  { accessorKey: 'recipe_name', header: 'recipe_name', size: 500 },
  { id: 'open', header: '', size: 380 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-2.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}

const recipeSubpath = (subpath: string) => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search/${subpath}`

const getRecipeDetailRoute = (recipeName: string) =>
  recipeDetailRoute(props.toolType, props.fab, 'open', recipeName)

const getLateralRoute = (recipeName: string) =>
  recipeDetailRoute(props.toolType, props.fab, 'lateral', recipeName)

const getMeasHistRoute = (recipeName: string) =>
  recipeDetailRoute(props.toolType, props.fab, 'meas-hist', recipeName)

const { selected, has, toggle, remove, clear, count } = useRecipeSelectionSet(props.toolType, props.fab)

const togglePageSelection = () => {
  const pageNames = pagedRows.value.map(row => row.recipe_name)
  const allSelected = pageNames.length > 0 && pageNames.every(name => has(name))
  if (allSelected) {
    pageNames.forEach(name => remove(name))
  } else {
    pageNames.forEach((name) => {
      if (!has(name)) toggle(name)
    })
  }
}

const firstSelected = computed(() => selected.value[0] ?? '')

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
  <div class="min-w-0 w-full space-y-4">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe 검색"
      subtitle="DB에 등록된 Recipe를 개별적으로 검색하거나, 여러 Recipe의 이미지를 한 번에 조회하여 손쉽게 비교할 수 있습니다."
      cadence="1일 주기"
      :stats="metaStats"
    />

    <!-- One 12-col grid with two stacked columns, not two full-width grid rows.
         Results must sit directly under the lookup card; when they lived in a
         separate grid row the tall 최근 검색 panel set the first row's height and
         pushed the results down, opening a gap beneath the search bar. items-start
         still keeps the short lookup card from stretching to the panel beside it. -->
    <div class="grid gap-4 xl:grid-cols-12 xl:items-start">
      <div class="flex min-w-0 flex-col gap-4 xl:col-span-8">
        <section class="dashboard-surface flex min-w-0 flex-col overflow-hidden rounded-(--sk-r-card)">
          <header class="border-b border-(--sk-border-soft) px-3 py-2.5">
            <p class="sk-eyebrow">
              RECIPE LOOKUP
            </p>
            <h2 class="mt-0.5 sk-title">
              검색어 입력
            </h2>
            <p class="mt-1 sk-meta">
              Recipe 이름의 전체 또는 일부를 입력해 조회합니다.
            </p>
          </header>

          <div class="p-3">
            <form
              class="flex min-w-0 items-center gap-2"
              @submit.prevent="commitSearch"
            >
              <UInput
                v-model="query"
                type="search"
                inputmode="search"
                autocomplete="off"
                class="min-w-0 flex-1"
                icon="i-lucide-search"
                placeholder="CD_MON"
                size="md"
                aria-label="Recipe 검색"
              >
                <template
                  v-if="query"
                  #trailing
                >
                  <UButton
                    type="button"
                    size="xs"
                    color="neutral"
                    variant="link"
                    icon="i-lucide-x"
                    aria-label="검색어 지우기"
                    @click="clearSearch"
                  />
                </template>
              </UInput>
              <UButton
                type="submit"
                class="shrink-0 bg-(--sk-ink) text-(--sk-ink-fg)"
                label="검색"
                icon="i-lucide-corner-down-left"
                size="md"
                :disabled="!canSearch"
              />
            </form>

            <div
              v-if="canSearch"
              class="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-(--sk-ink-muted)"
            >
              <span>{{ filteredCount.toLocaleString() }}개 검색됨 · 체크한 Recipe를 한 번에 열거나 비교할 수 있습니다.</span>
              <span
                v-if="refinedCount > 0"
                class="font-mono tabular-nums text-(--sk-ink-subtle)"
              >
                {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} / {{ refinedCount.toLocaleString() }}
              </span>
            </div>
            <div
              v-else
              class="mt-2.5 flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)"
            >
              <UIcon
                name="i-lucide-keyboard"
                class="h-3.5 w-3.5 shrink-0"
              />
              <span>검색어를 3자 이상 입력하면 결과가 표시됩니다 · 공백/_ 로 나눈 조각을 모두 포함하는 Recipe를 찾습니다.</span>
            </div>
          </div>
        </section>

        <main class="min-w-0">
          <div
            v-if="pending"
            class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
          >
            <UIcon
              name="i-lucide-loader-circle"
              class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
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
            <p class="mt-2 sk-body text-rose-600 dark:text-rose-300">
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

          <!-- Before a query exists the guidance lives inline in the lookup
               card above; render nothing here instead of a floating card. -->
          <template v-else-if="!canSearch" />

          <div
            v-else-if="filteredCount === 0"
            class="dashboard-surface rounded-2xl px-6 py-12 text-center"
          >
            <UIcon
              name="i-lucide-search-x"
              class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
            />
            <p class="mt-2 sk-body">
              검색 결과가 없습니다.
            </p>
            <p class="mt-1 sk-meta">
              다른 recipe 이름 조각을 입력해주세요.
            </p>
            <div
              v-if="historyMatches.length"
              class="mx-auto mt-4 max-w-md rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-left dark:border-amber-500/30 dark:bg-amber-500/10"
            >
              <p class="flex items-center gap-1.5 text-[11px] font-medium text-amber-700 dark:text-amber-300">
                <UIcon
                  name="i-lucide-history"
                  class="h-3.5 w-3.5 shrink-0"
                />
                redis에는 없지만 측정 기록은 발견됩니다. (redis update 주기 1일)
              </p>
              <p class="mt-1 font-mono text-[11px] text-amber-800/80 dark:text-amber-200/80">
                {{ historyMatchesLabel }}
              </p>
            </div>
          </div>

          <section
            v-else
            class="dashboard-surface rounded-2xl px-3.5 py-3"
          >
            <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <h2 class="sk-title">
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
                    class="h-3.5 w-3.5 shrink-0 text-(--sk-ink-muted)"
                  />
                  <input
                    v-model="tableFilter"
                    type="search"
                    autocomplete="off"
                    class="w-40 min-w-0 bg-transparent text-xs text-zinc-950 outline-none placeholder:text-(--sk-ink-muted) dark:text-zinc-50"
                    aria-label="Filter results"
                    placeholder="결과 내 필터"
                  >
                  <button
                    v-if="tableFilter"
                    type="button"
                    class="shrink-0 rounded-full p-0.5 text-(--sk-ink-muted) transition hover:bg-zinc-100 hover:text-(--sk-ink) dark:hover:bg-zinc-800"
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
                    class="mx-auto mb-1.5 h-5 w-5 text-(--sk-ink-muted)"
                  />
                  <p>필터 "<span class="font-mono text-zinc-700 dark:text-zinc-300">{{ tableFilter }}</span>"와 일치하는 recipe가 없습니다.</p>
                </div>
              </template>

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
                <span class="ml-2 text-(--sk-ink-muted)">
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
        </main>
      </div>

      <div class="flex min-w-0 flex-col gap-4 xl:col-span-4">
        <section class="dashboard-surface flex min-w-0 flex-col overflow-hidden rounded-(--sk-r-card)">
          <header class="border-b border-(--sk-border-soft) px-3 py-2.5">
            <p class="sk-eyebrow">
              RECENT SEARCHES
            </p>
            <div class="mt-0.5 flex items-center justify-between gap-2">
              <div class="flex items-baseline gap-2">
                <h2 class="sk-title">
                  최근 검색
                </h2>
                <span class="font-mono text-[10px] text-(--sk-ink-subtle)">{{ recentSearches.length }}</span>
              </div>
              <UButton
                v-if="recentSearches.length"
                size="xs"
                color="neutral"
                variant="ghost"
                label="전체 삭제"
                @click="clearRecentSearches"
              />
            </div>
            <p class="mt-1 sk-meta">
              최근 검색어를 선택하여 동일한 Recipe 목록을 다시 조회합니다.
            </p>
          </header>

          <div
            v-if="recentSearches.length"
            class="grid flex-1 content-start gap-1.5 p-3 sm:grid-cols-2"
          >
            <div
              v-for="(term, index) in recentSearches"
              :key="term"
              class="group flex min-w-0 items-center gap-1 rounded-(--sk-r-chip) border border-(--sk-border-soft) bg-(--sk-muted-surface) px-2 py-1.5 transition-colors hover:border-(--sk-brand)/35 hover:bg-(--sk-brand)/5"
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2 text-left"
                @click="applyRecentSearch(term)"
              >
                <span
                  class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-(--sk-brand)/10 font-mono text-[10px] font-semibold tabular-nums text-(--sk-brand)"
                >{{ index + 1 }}</span>
                <span class="truncate font-mono text-[11px] font-semibold text-(--sk-ink)">{{ term }}</span>
              </button>
              <button
                type="button"
                class="shrink-0 rounded p-0.5 text-(--sk-ink-subtle) opacity-60 transition hover:bg-(--sk-bad)/10 hover:text-(--sk-bad) group-hover:opacity-100"
                :aria-label="`${term} 최근 검색어 삭제`"
                @click.stop="removeRecentSearch(term)"
              >
                <UIcon
                  name="i-lucide-x"
                  class="h-3.5 w-3.5"
                />
              </button>
            </div>
          </div>
          <p
            v-else
            class="px-4 py-10 text-center sk-meta"
          >
            Recipe를 검색하면<br>최근 검색어가 여기에 표시됩니다.
          </p>
        </section>

        <aside class="min-w-0">
          <EbeamRecipeCompareSearchSelectTray
            :selected="selected"
            @remove="remove"
            @clear="clear"
            @compare="openSetCompare"
            @open="openSetDetail"
            @lateral="openSetLateral"
            @meas-hist="openSetMeasHist"
          />
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
