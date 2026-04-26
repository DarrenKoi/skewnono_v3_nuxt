<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { DeviceDescRow, R3DeviceGrpRow } from '~/composables/useDeviceStatisticsApi'

definePageMeta({
  hideFabSidebar: true
})

type DeviceRow = R3DeviceGrpRow | DeviceDescRow

const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fetchDeviceDesc, fetchR3DeviceGrp } = useDeviceStatisticsApi()

// Closed set of fac_id values used for device statistics filtering. Distinct from the open-ended
// fab_name space because device-statistics aggregates at the fac level.
type DeviceFab = 'R3' | 'M11' | 'M12' | 'M14' | 'M15' | 'M16'

const text = {
  title: '\ub514\ubc14\uc774\uc2a4 \ud1b5\uacc4',
  fabSelect: 'Fab \uc120\ud0dd',
  currentFab: '\ud604\uc7ac Fab',
  rFilter: '\uc5f0\uad6c\uc18c \ub514\ubc14\uc774\uc2a4 \ud544\ud130',
  mFilter: '\uc81c\uc870 \ub514\ubc14\uc774\uc2a4 \ud544\ud130',
  reset: '\ucd08\uae30\ud654',
  categorySearch: '\uce74\ud14c\uace0\ub9ac \uac80\uc0c9',
  lotSearch: 'Lot \uac80\uc0c9',
  noLots: '\uc120\ud0dd \uac00\ub2a5\ud55c Lot\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.',
  techSearch: 'Tech \uac80\uc0c9',
  deviceList: '\ub514\ubc14\uc774\uc2a4 \ubaa9\ub85d',
  csvDownload: 'CSV \ub2e4\uc6b4\ub85c\ub4dc',
  resetAll: '\uc804\uccb4 \ucd08\uae30\ud654',
  selectAll: '\uc804\uccb4 \uc120\ud0dd',
  clearAll: '\uc120\ud0dd \ud574\uc81c',
  tableSearch: '\ud14c\uc774\ube14 \uac80\uc0c9',
  allRows: '\uc804\uccb4',
  filteredRows: '\ud45c\uc2dc',
  activeFilters: '\ud544\ud130',
  moreOptionsSuffix: '\uac1c \ub354 \uc788\uc2b5\ub2c8\ub2e4. \uac80\uc0c9\uc73c\ub85c \uc881\ud600 \ubcf4\uc138\uc694.',
  loading: '\ub85c\ub529 \uc911',
  loadError: '\ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.',
  emptyRows: '\uc870\uac74\uc5d0 \ub9de\ub294 \ub514\ubc14\uc774\uc2a4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.',
  prev: '\uc774\uc804',
  next: '\ub2e4\uc74c'
} as const

const deviceFabOptions: { label: string, value: DeviceFab }[] = [
  { label: 'R3', value: 'R3' },
  { label: 'M16', value: 'M16' },
  { label: 'M15', value: 'M15' },
  { label: 'M14', value: 'M14' },
  { label: 'M12', value: 'M12' },
  { label: 'M11', value: 'M11' }
]

const deviceFabValues = deviceFabOptions.map(option => option.value)
const sortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const isDeviceFab = (value: string): value is DeviceFab => {
  return deviceFabValues.includes(value as DeviceFab)
}

// The URL's fab segment is now a fab_name (e.g. "M16A", "R3", "R4"). Device statistics filter by
// fac_id, so we collapse the fab_name into its parent fac_id before matching against DeviceFab.
const routeFab = computed<DeviceFab>(() => {
  const fabParam = String(route.params.fab ?? '').toUpperCase()
  const facId = fabNameToFacId(fabParam)

  return isDeviceFab(facId) ? facId : 'R3'
})

const SELECTED_FAB_STORAGE_KEY = 'skewnono:deviceStatistics.selectedFab'
const SELECTED_PROD_CATEGORIES_STORAGE_KEY = 'skewnono:deviceStatistics.selectedProdCategories'
const SELECTED_LOTS_STORAGE_KEY = 'skewnono:deviceStatistics.selectedLots'
const SELECTED_TECHS_STORAGE_KEY = 'skewnono:deviceStatistics.selectedTechs'
const MAX_VISIBLE_LOT_OPTIONS = 160

const readSavedFab = (): DeviceFab | null => {
  if (typeof window === 'undefined') return null
  try {
    const saved = window.localStorage.getItem(SELECTED_FAB_STORAGE_KEY)
    return saved && isDeviceFab(saved) ? saved : null
  } catch {
    return null
  }
}

const readSavedStringArray = (storageKey: string): string[] => {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : []
  } catch {
    return []
  }
}

const selectedFab = ref<DeviceFab>(readSavedFab() ?? routeFab.value)
const selectedProdCategories = ref<string[]>(readSavedStringArray(SELECTED_PROD_CATEGORIES_STORAGE_KEY))
const selectedLots = ref<string[]>(readSavedStringArray(SELECTED_LOTS_STORAGE_KEY))
const selectedTechs = ref<string[]>(readSavedStringArray(SELECTED_TECHS_STORAGE_KEY))
const prodCategorySearch = ref('')
const lotSearch = ref('')
const techSearch = ref('')
const tableSearch = ref('')
const currentPage = ref(1)
const pageSize = ref('25')

const { data, pending, error } = await useAsyncData<DeviceRow[]>(
  'device-statistics',
  () => {
    return selectedFab.value === 'R3'
      ? fetchR3DeviceGrp()
      : fetchDeviceDesc([selectedFab.value])
  },
  { watch: [selectedFab] }
)

const rows = computed(() => data.value ?? [])
const hasRSelection = computed(() => selectedFab.value === 'R3')
const hasMSelection = computed(() => selectedFab.value.startsWith('M'))
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const selectedFabLabel = computed(() => selectedFab.value)

const uniqueSorted = (values: string[]) => {
  return Array.from(new Set(values.map(value => value.trim()).filter(Boolean)))
    .sort((left, right) => sortCollator.compare(left, right))
}

const filterOptions = (options: string[], search: string) => {
  const searchTerm = search.trim().toLowerCase()

  if (!searchTerm) {
    return options
  }

  return options.filter(option => option.toLowerCase().includes(searchTerm))
}

// Narrow `rows` for each branch. Filtering by fac_id guards against the brief
// transition window where useAsyncData still holds the previous fab's rows
// while the new fetch is in flight.
const r3Rows = computed<R3DeviceGrpRow[]>(() => {
  if (!hasRSelection.value) return []
  return (rows.value as R3DeviceGrpRow[]).filter(row => row.fac_id === 'R3')
})
const mRows = computed<DeviceDescRow[]>(() => {
  if (!hasMSelection.value || !selectedFab.value) return []
  return (rows.value as DeviceDescRow[]).filter(row => row.fac_id === selectedFab.value)
})

const prodCategoryOptions = computed(() => uniqueSorted(r3Rows.value.map(row => row.prod_catg_cd)))

const r3RowsAfterCategory = computed(() => {
  if (selectedProdCategories.value.length === 0) {
    return r3Rows.value
  }

  return r3Rows.value.filter(row => selectedProdCategories.value.includes(row.prod_catg_cd))
})

const lotOptions = computed(() => uniqueSorted(r3RowsAfterCategory.value.map(row => row.lot_cd)))
const techOptions = computed(() => uniqueSorted(mRows.value.map(row => row.tech_nm)))
const visibleProdCategoryOptions = computed(() => filterOptions(prodCategoryOptions.value, prodCategorySearch.value))
const searchedLotOptions = computed(() => filterOptions(lotOptions.value, lotSearch.value))
const visibleLotOptions = computed(() => searchedLotOptions.value.slice(0, MAX_VISIBLE_LOT_OPTIONS))
const visibleLotOverflowCount = computed(() => Math.max(0, searchedLotOptions.value.length - visibleLotOptions.value.length))
const visibleTechOptions = computed(() => filterOptions(techOptions.value, techSearch.value))

const selectedProdCategorySet = computed(() => new Set(selectedProdCategories.value))
const selectedLotSet = computed(() => new Set(selectedLots.value))
const selectedTechSet = computed(() => new Set(selectedTechs.value))
const normalizedTableSearch = computed(() => tableSearch.value.trim().toLowerCase())

const isProdCategorySelected = (category: string) => selectedProdCategorySet.value.has(category)
const isLotSelected = (lot: string) => selectedLotSet.value.has(lot)
const isTechSelected = (tech: string) => selectedTechSet.value.has(tech)

const buildSearchText = (row: DeviceRow) => {
  return Object.values(row)
    .map(value => String(value).toLowerCase())
    .join('\u0000')
}

const matchesDomainFilters = (row: DeviceRow) => {
  if (row.fac_id !== selectedFab.value) {
    return false
  }

  if (hasRSelection.value) {
    const r3Row = row as R3DeviceGrpRow
    const matchesCategory = selectedProdCategories.value.length === 0
      || selectedProdCategorySet.value.has(r3Row.prod_catg_cd)
    const matchesLot = selectedLots.value.length === 0 || selectedLotSet.value.has(r3Row.lot_cd)

    return matchesCategory && matchesLot
  }

  const mRow = row as DeviceDescRow
  return selectedTechs.value.length === 0 || selectedTechSet.value.has(mRow.tech_nm)
}

const sortedRows = computed(() => {
  const sourceRows: DeviceRow[] = hasRSelection.value ? r3Rows.value : mRows.value

  return [...sourceRows].sort((left, right) => sortCollator.compare(left.lot_cd, right.lot_cd))
})

const indexedRows = computed(() => sortedRows.value.map(row => ({
  row,
  searchText: buildSearchText(row)
})))

const filteredRows = computed(() => {
  const searchTerm = normalizedTableSearch.value

  return indexedRows.value
    .filter(({ row, searchText }) => matchesDomainFilters(row) && (!searchTerm || searchText.includes(searchTerm)))
    .map(({ row }) => row)
})

const filteredRowCount = computed(() => filteredRows.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredRowCount.value / pageSizeNumber.value)))
const pageStart = computed(() => filteredRowCount.value === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1)
const pageEnd = computed(() => Math.min(currentPage.value * pageSizeNumber.value, filteredRowCount.value))
const pagedRows = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSizeNumber.value

  return filteredRows.value.slice(startIndex, startIndex + pageSizeNumber.value)
})

const pageSizeOptions = [
  { label: '25\uac1c', value: '25' },
  { label: '50\uac1c', value: '50' },
  { label: '100\uac1c', value: '100' }
]

const r3ColumnMetadata = [
  { key: 'fac_id', label: 'Fab', size: 72 },
  { key: 'plan_catg_type', label: 'Plan Catg', size: 96 },
  { key: 'prod_catg_cd', label: 'Category', size: 108 },
  { key: 'tech_cd', label: 'R Tech', size: 88 },
  { key: 'den_type', label: 'Density', size: 84 },
  { key: 'prod_grp_typ', label: 'Group', size: 120 },
  { key: 'gen_typ', label: 'Gen', size: 80 },
  { key: 'lot_cd', label: 'Lot', size: 92 },
  { key: 'plan_grade_cd', label: 'Grade', size: 76 },
  { key: 'ctn_desc', label: 'Description' }
] satisfies { key: keyof R3DeviceGrpRow, label: string, size?: number }[]

const deviceDescColumnMetadata = [
  { key: 'fac_id', label: 'Fab', size: 72 },
  { key: 'lot_cd', label: 'Lot', size: 100 },
  { key: 'tech_nm', label: 'Tech', size: 88 },
  { key: 'rnd_connector', label: 'R&D Connector', size: 124 },
  { key: 'chg_tm', label: 'Changed', size: 200 },
  { key: 'ctn_desc', label: 'Description' }
] satisfies { key: keyof DeviceDescRow, label: string, size?: number }[]

const columns = computed<TableColumn<DeviceRow>[]>(() => {
  const meta = hasRSelection.value ? r3ColumnMetadata : deviceDescColumnMetadata

  return meta.map(column => ({
    accessorKey: column.key as string,
    header: column.label,
    size: column.size
  }))
})

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

const toggleValue = (values: string[], value: string) => {
  return values.includes(value)
    ? values.filter(currentValue => currentValue !== value)
    : [...values, value]
}

const toggleFab = (fab: DeviceFab) => {
  selectedFab.value = fab
}

const toggleProdCategory = (category: string) => {
  selectedProdCategories.value = toggleValue(selectedProdCategories.value, category)
}

const toggleLot = (lot: string) => {
  selectedLots.value = toggleValue(selectedLots.value, lot)
}

const toggleTech = (tech: string) => {
  selectedTechs.value = toggleValue(selectedTechs.value, tech)
}

const allProdCategoriesSelected = computed(() => {
  return prodCategoryOptions.value.length > 0
    && selectedProdCategories.value.length === prodCategoryOptions.value.length
})

const allLotsSelected = computed(() => {
  return lotOptions.value.length > 0
    && selectedLots.value.length === lotOptions.value.length
})

const allTechsSelected = computed(() => {
  return techOptions.value.length > 0
    && selectedTechs.value.length === techOptions.value.length
})

const toggleAllProdCategories = () => {
  selectedProdCategories.value = allProdCategoriesSelected.value ? [] : [...prodCategoryOptions.value]
}

const toggleAllLots = () => {
  selectedLots.value = allLotsSelected.value ? [] : [...lotOptions.value]
}

const toggleAllTechs = () => {
  selectedTechs.value = allTechsSelected.value ? [] : [...techOptions.value]
}

const resetFabToRoute = () => {
  selectedFab.value = routeFab.value
}

const clearRFilters = () => {
  selectedProdCategories.value = []
  selectedLots.value = []
  prodCategorySearch.value = ''
  lotSearch.value = ''
}

const clearMFilters = () => {
  selectedTechs.value = []
  techSearch.value = ''
}

const resetAllFilters = () => {
  resetFabToRoute()
  clearRFilters()
  clearMFilters()
  tableSearch.value = ''
  currentPage.value = 1
}

const hasActiveFilters = computed(() => {
  return selectedFab.value !== routeFab.value
    || selectedProdCategories.value.length > 0
    || selectedLots.value.length > 0
    || selectedTechs.value.length > 0
    || prodCategorySearch.value.length > 0
    || lotSearch.value.length > 0
    || techSearch.value.length > 0
    || tableSearch.value.length > 0
})

const activeDomainFilterCount = computed(() => {
  if (hasRSelection.value) {
    return Number(selectedProdCategories.value.length > 0) + Number(selectedLots.value.length > 0)
  }

  return Number(selectedTechs.value.length > 0)
})

const activeFilterCount = computed(() => activeDomainFilterCount.value + (normalizedTableSearch.value ? 1 : 0))

const statCells = computed(() => [
  { label: 'Fab', value: selectedFabLabel.value, tone: 'text-zinc-900 dark:text-zinc-100' },
  { label: text.allRows, value: rows.value.length, tone: 'text-zinc-900 dark:text-zinc-100' },
  { label: text.filteredRows, value: filteredRowCount.value, tone: 'text-(--sk-accent)' },
  { label: text.activeFilters, value: activeFilterCount.value, tone: 'text-zinc-600 dark:text-zinc-300' }
])

const syncSelectionWithOptions = (selectedValues: string[], options: string[]) => {
  const optionSet = new Set(options)

  return selectedValues.filter(value => optionSet.has(value))
}

watch(selectedFab, (next) => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(SELECTED_FAB_STORAGE_KEY, next)
  } catch { /* noop */ }
})

const persistStringArray = (storageKey: string, values: string[]) => {
  if (typeof window === 'undefined') return
  try {
    if (values.length === 0) window.localStorage.removeItem(storageKey)
    else window.localStorage.setItem(storageKey, JSON.stringify(values))
  } catch { /* noop */ }
}

watch(selectedProdCategories, (next) => {
  persistStringArray(SELECTED_PROD_CATEGORIES_STORAGE_KEY, next)
})

watch(selectedLots, (next) => {
  persistStringArray(SELECTED_LOTS_STORAGE_KEY, next)
})

watch(selectedTechs, (next) => {
  persistStringArray(SELECTED_TECHS_STORAGE_KEY, next)
})

const escapeCsvValue = (value: unknown) => {
  const normalized = String(value ?? '').replace(/"/g, '""')
  return `"${normalized}"`
}

const getDeviceRowValue = (row: DeviceRow, key: string) => {
  return (row as unknown as Record<string, unknown>)[key]
}

const csvFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const fab = selectedFab.value.toLowerCase()
  return `cd-sem-${fab}-device-statistics-${today}.csv`
})

const downloadDeviceListCsv = () => {
  if (!import.meta.client || filteredRows.value.length === 0) return

  const meta = hasRSelection.value ? r3ColumnMetadata : deviceDescColumnMetadata
  const headerRow = meta.map(column => escapeCsvValue(column.label)).join(',')
  const bodyRows = filteredRows.value.map(row => (
    meta
      .map(column => escapeCsvValue(getDeviceRowValue(row, column.key as string)))
      .join(',')
  ))

  const csvContent = ['\uFEFF' + headerRow, ...bodyRows].join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = csvFileName.value
  link.click()

  URL.revokeObjectURL(url)
}

watch([prodCategoryOptions, lotOptions, techOptions, hasRSelection, hasMSelection], () => {
  // R3 selections are kept in memory across fab switches so they survive a quick R3 → M → R3
  // round-trip (and so the localStorage persistence isn't clobbered by an empty intermediate
  // state). They're hidden in the template via v-if="hasRSelection" and ignored by
  // matchesDomainFilters when on M, so leaving them populated is harmless. Only prune against
  // the live R3 option set when actually on R3.
  if (hasRSelection.value) {
    const nextCategories = syncSelectionWithOptions(selectedProdCategories.value, prodCategoryOptions.value)
    const nextLots = syncSelectionWithOptions(selectedLots.value, lotOptions.value)

    if (nextCategories.length !== selectedProdCategories.value.length) {
      selectedProdCategories.value = nextCategories
    }

    if (nextLots.length !== selectedLots.value.length) {
      selectedLots.value = nextLots
    }
  }

  // Same reasoning as the R3 selections above: keep techs in memory across fab switches so the
  // localStorage persistence isn't clobbered when the user briefly hops over to R3. The tech
  // filter UI is gated by v-else (i.e. !hasRSelection), and matchesDomainFilters ignores
  // selectedTechs on R3 rows. Only prune against the live tech option set when on an M-fab.
  if (hasMSelection.value) {
    const nextTechs = syncSelectionWithOptions(selectedTechs.value, techOptions.value)

    if (nextTechs.length !== selectedTechs.value.length) {
      selectedTechs.value = nextTechs
    }
  }
})

watch([filteredRowCount, pageSize], () => {
  if (currentPage.value > pageCount.value) {
    currentPage.value = pageCount.value
  }

  if (currentPage.value < 1) {
    currentPage.value = 1
  }
})

watch([selectedFab, selectedProdCategories, selectedLots, selectedTechs, tableSearch], () => {
  currentPage.value = 1
})

onMounted(() => {
  setToolType('cd-sem')
  setFab(routeFab.value)
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          CD-SEM
        </p>
        <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          {{ text.title }}
        </h1>
      </div>

      <div class="dashboard-surface flex overflow-hidden rounded-2xl self-start md:self-auto">
        <div
          v-for="(cell, index) in statCells"
          :key="cell.label"
          class="flex min-w-[72px] flex-col gap-0.5 px-4 py-2.5"
          :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }"
        >
          <span
            class="text-xl font-bold leading-none tabular-nums"
            :class="cell.tone"
          >{{ cell.value }}</span>
          <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
        </div>
      </div>
    </div>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ header: 'px-4 py-3 sm:px-4', body: 'px-4 py-4 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.fabSelect }}
          </h2>
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-map-pin"
            :label="text.currentFab"
            @click="resetFabToRoute"
          />
        </div>
      </template>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="fab in deviceFabOptions"
          :key="fab.value"
          type="button"
          class="inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium ring-1 transition-colors"
          :class="selectedFab === fab.value
            ? 'bg-zinc-900 text-zinc-50 ring-zinc-900 dark:bg-zinc-50 dark:text-zinc-950 dark:ring-zinc-50'
            : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
          @click="toggleFab(fab.value)"
        >
          {{ fab.label }}
        </button>
      </div>
    </UCard>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ header: 'px-4 py-3 sm:px-4', body: 'px-4 py-4 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ hasRSelection ? text.rFilter : text.mFilter }}
          </h2>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            :label="text.reset"
            :disabled="hasRSelection
              ? (selectedProdCategories.length === 0 && selectedLots.length === 0 && prodCategorySearch.length === 0 && lotSearch.length === 0)
              : (selectedTechs.length === 0 && techSearch.length === 0)"
            @click="hasRSelection ? clearRFilters() : clearMFilters()"
          />
        </div>
      </template>

      <div
        v-if="hasRSelection"
        class="grid gap-4 lg:grid-cols-[minmax(11rem,1fr)_minmax(22rem,2.5fr)]"
      >
        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              prod_catg_cd
            </p>
            <div class="flex items-center gap-2">
              <span class="text-xs text-zinc-500 tabular-nums">{{ selectedProdCategories.length }} / {{ prodCategoryOptions.length }}</span>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                :icon="allProdCategoriesSelected ? 'i-lucide-square' : 'i-lucide-check-square'"
                :label="allProdCategoriesSelected ? text.clearAll : text.selectAll"
                :disabled="prodCategoryOptions.length === 0"
                @click="toggleAllProdCategories"
              />
            </div>
          </div>
          <UInput
            v-model="prodCategorySearch"
            size="xs"
            color="neutral"
            variant="subtle"
            icon="i-lucide-search"
            :placeholder="text.categorySearch"
          />
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="category in visibleProdCategoryOptions"
              :key="category"
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium ring-1 transition-colors"
              :class="isProdCategorySelected(category)
                ? 'bg-emerald-600 text-white ring-emerald-600 dark:bg-emerald-400 dark:text-emerald-950 dark:ring-emerald-400'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="toggleProdCategory(category)"
            >
              <UIcon
                :name="isProdCategorySelected(category) ? 'i-lucide-check' : 'i-lucide-plus'"
                class="h-3.5 w-3.5"
              />
              {{ category }}
            </button>
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              lot_cd
            </p>
            <div class="flex items-center gap-2">
              <span class="text-xs text-zinc-500 tabular-nums">{{ selectedLots.length }} / {{ lotOptions.length }}</span>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                :icon="allLotsSelected ? 'i-lucide-square' : 'i-lucide-check-square'"
                :label="allLotsSelected ? text.clearAll : text.selectAll"
                :disabled="lotOptions.length === 0"
                @click="toggleAllLots"
              />
            </div>
          </div>
          <UInput
            v-model="lotSearch"
            size="xs"
            color="neutral"
            variant="subtle"
            icon="i-lucide-search"
            :placeholder="text.lotSearch"
          />
          <div class="max-h-48 overflow-y-auto rounded-lg border border-zinc-200/80 bg-white/70 p-2 dark:border-zinc-800 dark:bg-zinc-950/30">
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="lot in visibleLotOptions"
                :key="lot"
                type="button"
                class="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium ring-1 transition-colors"
                :class="isLotSelected(lot)
                  ? 'bg-sky-600 text-white ring-sky-600 dark:bg-sky-400 dark:text-sky-950 dark:ring-sky-400'
                  : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
                @click="toggleLot(lot)"
              >
                <UIcon
                  :name="isLotSelected(lot) ? 'i-lucide-check' : 'i-lucide-plus'"
                  class="h-3.5 w-3.5"
                />
                {{ lot }}
              </button>
            </div>
            <p
              v-if="visibleLotOverflowCount > 0"
              class="px-2 pt-2 text-xs text-zinc-500"
            >
              +{{ visibleLotOverflowCount }}{{ text.moreOptionsSuffix }}
            </p>
            <p
              v-if="visibleLotOptions.length === 0"
              class="px-2 py-4 text-center text-sm text-zinc-500"
            >
              {{ text.noLots }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-else
        class="space-y-2"
      >
        <div class="flex items-center justify-between gap-2">
          <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            tech_nm
          </p>
          <div class="flex items-center gap-2">
            <span class="text-xs text-zinc-500 tabular-nums">{{ selectedTechs.length }} / {{ techOptions.length }}</span>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              :icon="allTechsSelected ? 'i-lucide-square' : 'i-lucide-check-square'"
              :label="allTechsSelected ? text.clearAll : text.selectAll"
              :disabled="techOptions.length === 0"
              @click="toggleAllTechs"
            />
          </div>
        </div>
        <UInput
          v-model="techSearch"
          class="max-w-sm"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-search"
          :placeholder="text.techSearch"
        />
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="tech in visibleTechOptions"
            :key="tech"
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium ring-1 transition-colors"
            :class="isTechSelected(tech)
              ? 'bg-violet-600 text-white ring-violet-600 dark:bg-violet-400 dark:text-violet-950 dark:ring-violet-400'
              : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
            @click="toggleTech(tech)"
          >
            <UIcon
              :name="isTechSelected(tech) ? 'i-lucide-check' : 'i-lucide-plus'"
              class="h-3.5 w-3.5"
            />
            {{ tech }}
          </button>
        </div>
      </div>
    </UCard>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {{ text.deviceList }}
            </h2>
            <p class="text-xs text-zinc-500 tabular-nums">
              {{ pageStart }}-{{ pageEnd }} / {{ filteredRowCount }} rows
            </p>
          </div>
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-rotate-ccw"
            :label="text.resetAll"
            :disabled="!hasActiveFilters"
            @click="resetAllFilters"
          />
        </div>
      </template>

      <div class="flex flex-wrap items-center gap-2 border-b border-zinc-200/70 px-4 py-2.5 dark:border-zinc-800/70">
        <UInput
          v-model="tableSearch"
          class="min-w-[14rem] flex-1"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-search"
          :placeholder="text.tableSearch"
        />
        <USelect
          v-model="pageSize"
          class="w-[7rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="pageSizeOptions"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          :label="text.csvDownload"
          :disabled="filteredRowCount === 0"
          @click="downloadDeviceListCsv"
        />
      </div>

      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 px-4 py-12 text-sm text-zinc-500"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        {{ text.loading }}
      </div>
      <div
        v-else-if="error"
        class="px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <UTable
        v-else
        class="max-h-[34rem] font-mono-ids"
        :columns="columns"
        :data="pagedRows"
        :empty="text.emptyRows"
        :meta="tableMeta"
        sticky="header"
      >
        <template #ctn_desc-cell="{ row }">
          <span class="block max-w-[28rem] truncate text-zinc-600 dark:text-zinc-300">
            {{ row.original.ctn_desc }}
          </span>
        </template>
      </UTable>

      <div class="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
        <p class="text-xs text-zinc-500 tabular-nums">
          Page {{ currentPage }} / {{ pageCount }}
        </p>
        <div class="flex gap-2">
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-chevron-left"
            :label="text.prev"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            trailing-icon="i-lucide-chevron-right"
            :label="text.next"
            :disabled="currentPage >= pageCount"
            @click="currentPage += 1"
          />
        </div>
      </div>
    </UCard>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td) {
  font-size: 12.5px;
}

/* ctn_desc is always the last column in both R3 and device_desc layouts and
   is the only prose field. Mono everything else regardless of column count. */
.font-mono-ids :deep(td:not(:last-child)) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
