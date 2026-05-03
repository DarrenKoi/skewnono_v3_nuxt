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
  title: '디바이스 통계',
  fabSelect: 'Fab',
  reset: '초기화',
  lotSearch: 'Lot 검색 (예: R0A2)',
  techSearch: 'Tech 검색',
  csvDownload: 'CSV 다운로드',
  resetAll: '전체 초기화',
  clearAll: '전체 해제',
  tableSearch: '테이블 검색',
  allRows: '전체',
  filteredRows: '표시',
  activeFilters: '필터',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  emptyRows: '조건에 맞는 디바이스가 없습니다.',
  prev: '이전',
  next: '다음',
  step1Title: '빠른 필터',
  step1HintR: '카테고리 / Lot으로 좁히기',
  step1HintM: 'Tech로 좁히기',
  step2Title: '디바이스 선택',
  step2Hint: '체크박스로 여러 개 선택',
  step3Title: '비교 + 이동',
  step3Hint: '선택된 디바이스',
  emptySelectionTitle: '디바이스 비교 시작하기',
  emptySelectionDescLineOne: '왼쪽 테이블에서',
  emptySelectionDescLineTwo: '2개 이상 선택해 보세요',
  ctaEmpty: '디바이스를 선택하세요',
  ctaSingle: '디바이스 통계 보기',
  ctaMulti: '{count}개 비교 페이지로',
  toastTitle: '{count}개 디바이스 선택됨',
  overflowSuffix: '외 {count}개'
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
const SELECTED_DEVICE_LOTS_STORAGE_KEY = 'skewnono:deviceStatistics.selectedDeviceLots'
// Step 1 keeps the lot/tech chip strips compact: surface a small budget of unselected options,
// always paired with any currently-selected ones so they remain togglable from the strip.
const STEP1_LOT_CHIP_BUDGET = 24
const STEP1_TECH_CHIP_BUDGET = 24

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
// Step 3 cart selection — independent from the Step 1 lot/tech filters.
const selectedDeviceLots = ref<string[]>(readSavedStringArray(SELECTED_DEVICE_LOTS_STORAGE_KEY))
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
const searchedLotOptions = computed(() => filterOptions(lotOptions.value, lotSearch.value))
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
  { label: '25개', value: '25' },
  { label: '50개', value: '50' },
  { label: '100개', value: '100' }
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

  return [
    {
      id: 'select',
      header: '',
      size: 40,
      enableSorting: false,
      enableHiding: false
    },
    ...meta.map(column => ({
      accessorKey: column.key as string,
      header: column.label,
      size: column.size
    }))
  ]
})

const tableMeta = {
  class: {
    tr: 'cursor-pointer select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

const toggleValue = (values: string[], value: string) => {
  return values.includes(value)
    ? values.filter(currentValue => currentValue !== value)
    : [...values, value]
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

const selectedDeviceLotSet = computed(() => new Set(selectedDeviceLots.value))
const isDeviceSelected = (lot: string) => selectedDeviceLotSet.value.has(lot)

const toggleDeviceSelect = (lot: string) => {
  selectedDeviceLots.value = toggleValue(selectedDeviceLots.value, lot)
}

const clearDeviceSelection = () => {
  selectedDeviceLots.value = []
}

// Preserve selection order so the Step 3 cart shows lots in the order the user added them.
const filteredRowMap = computed(() => {
  const map = new Map<string, DeviceRow>()

  for (const row of filteredRows.value) {
    map.set(row.lot_cd, row)
  }

  return map
})

const sortedRowMap = computed(() => {
  const map = new Map<string, DeviceRow>()

  for (const row of sortedRows.value) {
    map.set(row.lot_cd, row)
  }

  return map
})

const selectedDeviceRows = computed<DeviceRow[]>(() => {
  return selectedDeviceLots.value
    .map(lot => sortedRowMap.value.get(lot) ?? filteredRowMap.value.get(lot))
    .filter((row): row is DeviceRow => Boolean(row))
})

const allOnPageSelected = computed(() => {
  return pagedRows.value.length > 0
    && pagedRows.value.every(row => selectedDeviceLotSet.value.has(row.lot_cd))
})

const togglePageSelection = () => {
  if (allOnPageSelected.value) {
    const onPage = new Set(pagedRows.value.map(row => row.lot_cd))
    selectedDeviceLots.value = selectedDeviceLots.value.filter(lot => !onPage.has(lot))
    return
  }

  const next = [...selectedDeviceLots.value]

  for (const row of pagedRows.value) {
    if (!selectedDeviceLotSet.value.has(row.lot_cd)) {
      next.push(row.lot_cd)
    }
  }

  selectedDeviceLots.value = next
}

const stepOneLotChips = computed<string[]>(() => {
  const selectedSet = selectedLotSet.value
  const selectedFromOptions = lotOptions.value.filter(lot => selectedSet.has(lot))
  const remainingBudget = Math.max(0, STEP1_LOT_CHIP_BUDGET - selectedFromOptions.length)
  const matchedUnselected = searchedLotOptions.value.filter(lot => !selectedSet.has(lot))

  return [...selectedFromOptions, ...matchedUnselected.slice(0, remainingBudget)]
})

const stepOneLotOverflowCount = computed(() => {
  const selectedSet = selectedLotSet.value
  const matchedUnselected = searchedLotOptions.value.filter(lot => !selectedSet.has(lot))
  const selectedFromOptions = lotOptions.value.filter(lot => selectedSet.has(lot))
  const remainingBudget = Math.max(0, STEP1_LOT_CHIP_BUDGET - selectedFromOptions.length)

  return Math.max(0, matchedUnselected.length - remainingBudget)
})

const stepOneTechChips = computed<string[]>(() => {
  const selectedSet = selectedTechSet.value
  const selectedFromOptions = techOptions.value.filter(tech => selectedSet.has(tech))
  const remainingBudget = Math.max(0, STEP1_TECH_CHIP_BUDGET - selectedFromOptions.length)
  const matchedUnselected = visibleTechOptions.value.filter(tech => !selectedSet.has(tech))

  return [...selectedFromOptions, ...matchedUnselected.slice(0, remainingBudget)]
})

const stepOneTechOverflowCount = computed(() => {
  const selectedSet = selectedTechSet.value
  const matchedUnselected = visibleTechOptions.value.filter(tech => !selectedSet.has(tech))
  const selectedFromOptions = techOptions.value.filter(tech => selectedSet.has(tech))
  const remainingBudget = Math.max(0, STEP1_TECH_CHIP_BUDGET - selectedFromOptions.length)

  return Math.max(0, matchedUnselected.length - remainingBudget)
})

const deviceChipLabel = (row: DeviceRow): string => {
  if ('prod_catg_cd' in row && row.prod_catg_cd) {
    const tech = (row as R3DeviceGrpRow).tech_cd

    return tech ? `${row.prod_catg_cd} · ${tech}` : row.prod_catg_cd
  }

  const tech = (row as DeviceDescRow).tech_nm

  return tech ? `${row.fac_id} · ${tech}` : row.fac_id
}

const toast = useToast()

const proceedToStatistics = async () => {
  if (selectedDeviceLots.value.length === 0) return

  const preview = selectedDeviceLots.value.slice(0, 6).join(', ')
  const overflow = selectedDeviceLots.value.length - 6

  toast.add({
    title: text.toastTitle.replace('{count}', String(selectedDeviceLots.value.length)),
    description: overflow > 0 ? `${preview} ${text.overflowSuffix.replace('{count}', String(overflow))}` : preview,
    icon: 'i-lucide-arrow-right',
    color: 'primary'
  })

  await navigateTo(`/ebeam/cd-sem/${route.params.fab}/device-statistics/comparison`)
}

const ctaLabel = computed(() => {
  if (selectedDeviceLots.value.length === 0) return text.ctaEmpty
  if (selectedDeviceLots.value.length === 1) return text.ctaSingle

  return text.ctaMulti.replace('{count}', String(selectedDeviceLots.value.length))
})

const resetAllFilters = () => {
  selectedFab.value = routeFab.value
  selectedProdCategories.value = []
  selectedLots.value = []
  selectedTechs.value = []
  lotSearch.value = ''
  techSearch.value = ''
  tableSearch.value = ''
  currentPage.value = 1
}

const hasActiveFilters = computed(() => {
  return selectedFab.value !== routeFab.value
    || selectedProdCategories.value.length > 0
    || selectedLots.value.length > 0
    || selectedTechs.value.length > 0
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

watch(selectedDeviceLots, (next) => {
  persistStringArray(SELECTED_DEVICE_LOTS_STORAGE_KEY, next)
})

// Clear the Step 3 cart whenever the user actively switches fab — devices belong to a single
// fab in this UI, so carrying selections across fabs would be confusing. Initial-load mismatches
// are pruned by the watcher on `pending`/`sortedRows` below.
watch(selectedFab, () => {
  selectedDeviceLots.value = []
})

watch([sortedRows, pending], ([nextSortedRows, nextPending]) => {
  if (nextPending) return
  if (selectedDeviceLots.value.length === 0) return

  const validLots = new Set(nextSortedRows.map(row => row.lot_cd))

  if (validLots.size === 0) return

  const pruned = selectedDeviceLots.value.filter(lot => validLots.has(lot))

  if (pruned.length !== selectedDeviceLots.value.length) {
    selectedDeviceLots.value = pruned
  }
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
  <div class="space-y-3">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <div class="min-w-0">
          <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            CD-SEM
          </p>
          <h1 class="text-2xl font-bold whitespace-nowrap text-zinc-950 dark:text-zinc-50">
            {{ text.title }}
          </h1>
        </div>
        <div class="hidden h-9 w-px self-end mb-1 bg-zinc-200 dark:bg-zinc-700 md:block" />
        <div
          role="radiogroup"
          :aria-label="text.fabSelect"
          class="flex flex-wrap items-center gap-1 self-end mb-1.5"
        >
          <button
            v-for="option in deviceFabOptions"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="selectedFab === option.value"
            class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
            :class="selectedFab === option.value
              ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
              : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
            @click="selectedFab = option.value"
          >
            {{ option.label }}
          </button>
        </div>
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

    <!-- Step 1 — Quick filter strip -->
    <div class="dashboard-surface rounded-2xl px-3.5 py-2.5">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-(--sk-accent) font-mono text-[10px] font-bold text-white">1</span>
          <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.step1Title }}
          </h3>
          <span class="text-[10.5px] text-zinc-400 dark:text-zinc-500">
            {{ hasRSelection ? text.step1HintR : text.step1HintM }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="hasActiveFilters"
            class="inline-flex h-5 items-center rounded bg-(--sk-accent-tint) px-1.5 font-mono text-[9.5px] tabular-nums text-(--sk-accent)"
          >
            {{ filteredRowCount.toLocaleString() }} / {{ rows.length.toLocaleString() }}
          </span>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            :label="text.reset"
            :disabled="!hasActiveFilters"
            @click="resetAllFilters"
          />
        </div>
      </div>

      <div
        v-if="hasRSelection"
        class="flex flex-col gap-2 xl:grid xl:grid-cols-12"
      >
        <div class="flex items-start gap-2 min-w-0 xl:col-span-4">
          <span class="mt-1.5 font-mono text-[10px] text-zinc-400 shrink-0">prod_catg_cd</span>
          <div class="flex flex-wrap items-center gap-1">
            <button
              v-for="category in prodCategoryOptions"
              :key="category"
              type="button"
              class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
              :class="isProdCategorySelected(category)
                ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="toggleProdCategory(category)"
            >
              {{ category }}
            </button>
          </div>
        </div>

        <div class="flex items-start gap-2 min-w-0 xl:col-span-8">
          <span class="mt-1.5 font-mono text-[10px] text-zinc-400 shrink-0">lot_cd</span>
          <UInput
            v-model="lotSearch"
            class="w-44 shrink-0"
            size="xs"
            color="neutral"
            variant="subtle"
            icon="i-lucide-search"
            :placeholder="text.lotSearch"
          />
          <div class="flex flex-wrap items-center gap-1 min-w-0">
            <button
              v-for="lot in stepOneLotChips"
              :key="lot"
              type="button"
              class="inline-flex h-6 items-center gap-1 rounded-md px-2 font-mono text-[11px] font-medium ring-1 transition-colors"
              :class="isLotSelected(lot)
                ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="toggleLot(lot)"
            >
              {{ lot }}
            </button>
            <span
              v-if="stepOneLotOverflowCount > 0"
              class="font-mono text-[10px] text-zinc-400 dark:text-zinc-500"
            >
              +{{ stepOneLotOverflowCount }}
            </span>
          </div>
        </div>
      </div>

      <div
        v-else
        class="flex items-start gap-2 min-w-0"
      >
        <span class="mt-1.5 font-mono text-[10px] text-zinc-400 shrink-0">tech_nm</span>
        <UInput
          v-model="techSearch"
          class="w-44 shrink-0"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-search"
          :placeholder="text.techSearch"
        />
        <div class="flex flex-wrap items-center gap-1 min-w-0">
          <button
            v-for="tech in stepOneTechChips"
            :key="tech"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
            :class="isTechSelected(tech)
              ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
              : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
            @click="toggleTech(tech)"
          >
            {{ tech }}
          </button>
          <span
            v-if="stepOneTechOverflowCount > 0"
            class="font-mono text-[10px] text-zinc-400 dark:text-zinc-500"
          >
            +{{ stepOneTechOverflowCount }}
          </span>
        </div>
      </div>
    </div>

    <!-- Step 2 (table) + Step 3 (cart) -->
    <div class="grid grid-cols-12 gap-3">
      <div class="col-span-12 space-y-2 lg:col-span-8">
        <div class="flex items-center gap-2 px-1">
          <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-(--sk-accent) font-mono text-[10px] font-bold text-white">2</span>
          <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.step2Title }}
          </h3>
          <span class="text-[10.5px] text-zinc-400 dark:text-zinc-500">
            {{ text.step2Hint }}
          </span>
        </div>

        <UCard
          class="dashboard-surface rounded-2xl"
          :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-xs text-zinc-500 tabular-nums">
                {{ pageStart }}-{{ pageEnd }} / {{ filteredRowCount }} rows
              </p>
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
            @select="(_, row) => toggleDeviceSelect(row.original.lot_cd)"
          >
            <template #select-header>
              <input
                type="checkbox"
                :checked="allOnPageSelected"
                :aria-label="text.step2Hint"
                class="h-3.5 w-3.5 rounded accent-(--sk-accent)"
                @change="togglePageSelection"
              >
            </template>
            <template #select-cell="{ row }">
              <input
                type="checkbox"
                :checked="isDeviceSelected(row.original.lot_cd)"
                class="h-3.5 w-3.5 rounded accent-(--sk-accent)"
                @click.stop
                @change="toggleDeviceSelect(row.original.lot_cd)"
              >
            </template>
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

      <div class="col-span-12 space-y-2 lg:col-span-4">
        <div class="flex items-center gap-2 px-1">
          <span
            class="inline-flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-bold transition-colors"
            :class="selectedDeviceLots.length > 0
              ? 'bg-(--sk-accent) text-white'
              : 'bg-zinc-200 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400'"
          >3</span>
          <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.step3Title }}
          </h3>
          <span class="text-[10.5px] text-zinc-400 dark:text-zinc-500">
            {{ text.step3Hint }}
          </span>
        </div>

        <UCard
          class="dashboard-surface sticky top-2 overflow-hidden rounded-2xl"
          :ui="{ body: 'p-0 sm:p-0' }"
        >
          <div class="max-h-[28rem] overflow-y-auto">
            <div
              v-if="selectedDeviceRows.length === 0"
              class="px-4 py-10 text-center"
            >
              <div class="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-50 text-zinc-400 ring-1 ring-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800">
                <UIcon
                  name="i-lucide-plus"
                  class="h-4 w-4"
                />
              </div>
              <p class="text-[11.5px] font-medium leading-snug text-zinc-600 dark:text-zinc-300">
                {{ text.emptySelectionTitle }}
              </p>
              <p class="mt-1 text-[10.5px] leading-snug text-zinc-400 dark:text-zinc-500">
                {{ text.emptySelectionDescLineOne }}<br>{{ text.emptySelectionDescLineTwo }}
              </p>
            </div>
            <div
              v-else
              class="divide-y divide-zinc-100 dark:divide-zinc-800"
            >
              <div
                v-for="(row, index) in selectedDeviceRows"
                :key="row.lot_cd"
                class="group flex items-center gap-2 px-3.5 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
              >
                <span class="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-zinc-100 font-mono text-[9px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                  {{ index + 1 }}
                </span>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="font-mono text-[12px] font-semibold text-zinc-900 dark:text-zinc-100">{{ row.lot_cd }}</span>
                    <span class="text-[9.5px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                      {{ deviceChipLabel(row) }}
                    </span>
                  </div>
                  <p class="truncate text-[10px] text-zinc-500 dark:text-zinc-400">
                    {{ row.ctn_desc }}
                  </p>
                </div>
                <button
                  type="button"
                  class="shrink-0 text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-zinc-900 dark:hover:text-zinc-100"
                  :aria-label="text.clearAll"
                  @click="toggleDeviceSelect(row.lot_cd)"
                >
                  <UIcon
                    name="i-lucide-x"
                    class="h-3 w-3"
                  />
                </button>
              </div>
            </div>
          </div>

          <div class="space-y-2 border-t border-zinc-100 bg-zinc-50/40 p-2.5 dark:border-zinc-800 dark:bg-zinc-900/30">
            <UButton
              block
              size="md"
              :disabled="selectedDeviceLots.length === 0"
              :trailing-icon="selectedDeviceLots.length > 0 ? 'i-lucide-arrow-right' : undefined"
              class="bg-(--sk-accent) text-white ring-1 ring-(--sk-accent) hover:bg-(--sk-accent)/90 disabled:opacity-50"
              :ui="{ label: 'flex-1 text-center' }"
              @click="proceedToStatistics"
            >
              {{ ctaLabel }}
            </UButton>
            <button
              v-if="selectedDeviceLots.length > 0"
              type="button"
              class="block w-full text-center text-[10.5px] text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
              @click="clearDeviceSelection"
            >
              {{ text.clearAll }}
            </button>
          </div>
        </UCard>
      </div>
    </div>
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
