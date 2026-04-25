<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { DeviceStatisticsRow, DeviceStatisticsSource } from '~/composables/useDeviceStatisticsApi'
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fetchDeviceStatisticsRows } = useDeviceStatisticsApi()

type DeviceFab = Exclude<Fab, 'all'>

const text = {
  title: '\ub514\ubc14\uc774\uc2a4 \ud1b5\uacc4',
  fabSelect: 'Fab \uc120\ud0dd',
  all: '\uc804\uccb4',
  currentFab: '\ud604\uc7ac Fab',
  displayedRows: '\ud45c\uc2dc Row',
  rFilter: 'R \uacc4\uc5f4 \ud544\ud130',
  mFilter: 'M \uacc4\uc5f4 \ud544\ud130',
  reset: '\ucd08\uae30\ud654',
  categorySearch: '\uce74\ud14c\uace0\ub9ac \uac80\uc0c9',
  lotSearch: 'Lot \uac80\uc0c9',
  noLots: '\uc120\ud0dd \uac00\ub2a5\ud55c Lot\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.',
  techSearch: 'Tech \uac80\uc0c9',
  deviceList: '\ub514\ubc14\uc774\uc2a4 \ubaa9\ub85d',
  resetAll: '\uc804\uccb4 \ucd08\uae30\ud654',
  tableSearch: '\ud14c\uc774\ube14 \uac80\uc0c9',
  loading: '\ub85c\ub529 \uc911',
  loadError: '\ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.',
  emptyRows: '\uc870\uac74\uc5d0 \ub9de\ub294 \ub514\ubc14\uc774\uc2a4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.',
  prev: '\uc774\uc804',
  next: '\ub2e4\uc74c'
} as const

const deviceFabOptions: { label: string, value: DeviceFab }[] = [
  { label: 'R3', value: 'R3' },
  { label: 'M11', value: 'M11' },
  { label: 'M12', value: 'M12' },
  { label: 'M14', value: 'M14' },
  { label: 'M15', value: 'M15' },
  { label: 'M16', value: 'M16' }
]

const deviceFabValues = deviceFabOptions.map(option => option.value)
const sortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const isDeviceFab = (value: string): value is DeviceFab => {
  return deviceFabValues.includes(value as DeviceFab)
}

const routeFab = computed<DeviceFab>(() => {
  const fabParam = String(route.params.fab ?? '').toUpperCase()

  return isDeviceFab(fabParam) ? fabParam : 'R3'
})

const selectedFabs = ref<DeviceFab[]>([routeFab.value])
const selectedProdCategories = ref<string[]>([])
const selectedLots = ref<string[]>([])
const selectedTechs = ref<string[]>([])
const prodCategorySearch = ref('')
const lotSearch = ref('')
const techSearch = ref('')
const tableSearch = ref('')
const currentPage = ref(1)
const pageSize = ref('25')

const { data, pending, error } = await useAsyncData(
  'device-statistics',
  () => fetchDeviceStatisticsRows(selectedFabs.value),
  { watch: [selectedFabs] }
)

const rows = computed(() => data.value ?? [])
const hasRSelection = computed(() => selectedFabs.value.includes('R3'))
const hasMSelection = computed(() => selectedFabs.value.some(fab => fab.startsWith('M')))
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const selectedFabLabel = computed(() => selectedFabs.value.join(', '))

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

const r3Rows = computed(() => rows.value.filter(row => row.source === 'r3_device_grp'))
const mRows = computed(() => rows.value.filter(row => row.source === 'device_desc'))

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
const visibleLotOptions = computed(() => filterOptions(lotOptions.value, lotSearch.value))
const visibleTechOptions = computed(() => filterOptions(techOptions.value, techSearch.value))
const selectedFabSet = computed(() => new Set(selectedFabs.value))

const matchesSearch = (row: DeviceStatisticsRow) => {
  const searchTerm = tableSearch.value.trim().toLowerCase()

  if (!searchTerm) {
    return true
  }

  return Object.values(row).some(value => value.toLowerCase().includes(searchTerm))
}

const matchesDomainFilters = (row: DeviceStatisticsRow) => {
  if (!selectedFabSet.value.has(row.fac_id as DeviceFab)) {
    return false
  }

  if (row.source === 'r3_device_grp') {
    const matchesCategory = selectedProdCategories.value.length === 0
      || selectedProdCategories.value.includes(row.prod_catg_cd)
    const matchesLot = selectedLots.value.length === 0 || selectedLots.value.includes(row.lot_cd)

    return matchesCategory && matchesLot
  }

  if (row.source === 'device_desc') {
    return selectedTechs.value.length === 0 || selectedTechs.value.includes(row.tech_nm)
  }

  return true
}

const filteredRows = computed(() => {
  return rows.value
    .filter(row => matchesDomainFilters(row) && matchesSearch(row))
    .sort((left, right) => {
      const facCompare = sortCollator.compare(left.fac_id, right.fac_id)

      if (facCompare !== 0) {
        return facCompare
      }

      return sortCollator.compare(left.lot_cd, right.lot_cd)
    })
})

const filteredRowCount = computed(() => filteredRows.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredRowCount.value / pageSizeNumber.value)))
const pageStart = computed(() => filteredRowCount.value === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1)
const pageEnd = computed(() => Math.min(currentPage.value * pageSizeNumber.value, filteredRowCount.value))
const pagedRows = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSizeNumber.value

  return filteredRows.value.slice(startIndex, startIndex + pageSizeNumber.value)
})

const rowSummary = computed(() => {
  const r3Count = filteredRows.value.filter(row => row.source === 'r3_device_grp').length
  const mCount = filteredRows.value.length - r3Count
  const lotCount = new Set(filteredRows.value.map(row => row.lot_cd).filter(Boolean)).size
  const techCount = new Set(filteredRows.value.map(row => row.tech_nm).filter(Boolean)).size

  return {
    r3Count,
    mCount,
    lotCount,
    techCount
  }
})

const pageSizeOptions = [
  { label: '25\uac1c', value: '25' },
  { label: '50\uac1c', value: '50' },
  { label: '100\uac1c', value: '100' }
]

const tableColumnMetadata = [
  { key: 'source', label: 'Source', size: 112 },
  { key: 'fac_id', label: 'Fab', size: 72 },
  { key: 'prod_catg_cd', label: 'Category', size: 108 },
  { key: 'lot_cd', label: 'Lot', size: 92 },
  { key: 'tech_nm', label: 'Tech', size: 76 },
  { key: 'tech_cd', label: 'R Tech', size: 88 },
  { key: 'plan_grade_cd', label: 'Grade', size: 76 },
  { key: 'lake_load_tm', label: 'Lake Time', size: 132 },
  { key: 'chg_tm', label: 'Changed', size: 156 },
  { key: 'ctn_desc', label: 'Description' }
] satisfies { key: keyof DeviceStatisticsRow, label: string, size?: number }[]

const columns = tableColumnMetadata.map(column => ({
  accessorKey: column.key,
  header: column.label,
  size: column.size
})) satisfies TableColumn<DeviceStatisticsRow>[]

const getSourceLabel = (source: DeviceStatisticsSource) => {
  return source === 'r3_device_grp' ? 'R3 Device Group' : 'Device Desc'
}

const toggleValue = (values: string[], value: string) => {
  return values.includes(value)
    ? values.filter(currentValue => currentValue !== value)
    : [...values, value]
}

const toggleFab = (fab: DeviceFab) => {
  if (selectedFabSet.value.has(fab)) {
    if (selectedFabs.value.length > 1) {
      selectedFabs.value = selectedFabs.value.filter(selectedFab => selectedFab !== fab)
    }

    return
  }

  selectedFabs.value = [...selectedFabs.value, fab].sort((left, right) => sortCollator.compare(left, right))
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

const selectAllFabs = () => {
  selectedFabs.value = [...deviceFabValues]
}

const resetFabToRoute = () => {
  selectedFabs.value = [routeFab.value]
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
  return selectedFabs.value.length !== 1
    || selectedFabs.value[0] !== routeFab.value
    || selectedProdCategories.value.length > 0
    || selectedLots.value.length > 0
    || selectedTechs.value.length > 0
    || prodCategorySearch.value.length > 0
    || lotSearch.value.length > 0
    || techSearch.value.length > 0
    || tableSearch.value.length > 0
})

const syncSelectionWithOptions = (selectedValues: string[], options: string[]) => {
  const optionSet = new Set(options)

  return selectedValues.filter(value => optionSet.has(value))
}

watch(routeFab, (nextFab) => {
  selectedFabs.value = [nextFab]
})

watch([prodCategoryOptions, lotOptions, techOptions, hasRSelection, hasMSelection], () => {
  if (!hasRSelection.value) {
    selectedProdCategories.value = []
    selectedLots.value = []
  } else {
    const nextCategories = syncSelectionWithOptions(selectedProdCategories.value, prodCategoryOptions.value)
    const nextLots = syncSelectionWithOptions(selectedLots.value, lotOptions.value)

    if (nextCategories.length !== selectedProdCategories.value.length) {
      selectedProdCategories.value = nextCategories
    }

    if (nextLots.length !== selectedLots.value.length) {
      selectedLots.value = nextLots
    }
  }

  if (!hasMSelection.value) {
    selectedTechs.value = []
  } else {
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

watch([selectedFabs, selectedProdCategories, selectedLots, selectedTechs, tableSearch], () => {
  currentPage.value = 1
})

onMounted(() => {
  setToolType('cd-sem')
  setFab(routeFab.value)
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          CD-SEM
        </p>
        <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          {{ text.title }}
        </h1>
      </div>
      <p class="text-sm text-zinc-500 dark:text-zinc-400">
        {{ selectedFabLabel }}
      </p>
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
          <div class="flex gap-2">
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              icon="i-lucide-layers-3"
              :label="text.all"
              @click="selectAllFabs"
            />
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              icon="i-lucide-map-pin"
              :label="text.currentFab"
              @click="resetFabToRoute"
            />
          </div>
        </div>
      </template>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="fab in deviceFabOptions"
          :key="fab.value"
          type="button"
          class="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium ring-1 transition-colors"
          :class="selectedFabSet.has(fab.value)
            ? 'bg-zinc-900 text-zinc-50 ring-zinc-900 dark:bg-zinc-50 dark:text-zinc-950 dark:ring-zinc-50'
            : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
          @click="toggleFab(fab.value)"
        >
          <UIcon
            :name="selectedFabSet.has(fab.value) ? 'i-lucide-check-square' : 'i-lucide-square'"
            class="h-4 w-4"
          />
          {{ fab.label }}
        </button>
      </div>
    </UCard>

    <div class="grid gap-3 md:grid-cols-4">
      <div class="dashboard-surface rounded-2xl px-4 py-3">
        <p class="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          {{ text.displayedRows }}
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
          {{ filteredRowCount }}
        </p>
      </div>
      <div class="dashboard-surface rounded-2xl px-4 py-3">
        <p class="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          R3 Row
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
          {{ rowSummary.r3Count }}
        </p>
      </div>
      <div class="dashboard-surface rounded-2xl px-4 py-3">
        <p class="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          M Row
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
          {{ rowSummary.mCount }}
        </p>
      </div>
      <div class="dashboard-surface rounded-2xl px-4 py-3">
        <p class="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          Lot / Tech
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
          {{ rowSummary.lotCount }} / {{ rowSummary.techCount }}
        </p>
      </div>
    </div>

    <UCard
      v-if="hasRSelection"
      class="dashboard-surface rounded-2xl"
      :ui="{ header: 'px-4 py-3 sm:px-4', body: 'px-4 py-4 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.rFilter }}
          </h2>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            :label="text.reset"
            :disabled="selectedProdCategories.length === 0 && selectedLots.length === 0 && prodCategorySearch.length === 0 && lotSearch.length === 0"
            @click="clearRFilters"
          />
        </div>
      </template>

      <div class="grid gap-4 lg:grid-cols-[minmax(14rem,0.85fr)_minmax(18rem,1.15fr)]">
        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              prod_catg_cd
            </p>
            <span class="text-xs text-zinc-500 tabular-nums">{{ selectedProdCategories.length }} / {{ prodCategoryOptions.length }}</span>
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
              :class="selectedProdCategories.includes(category)
                ? 'bg-emerald-600 text-white ring-emerald-600 dark:bg-emerald-400 dark:text-emerald-950 dark:ring-emerald-400'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="toggleProdCategory(category)"
            >
              <UIcon
                :name="selectedProdCategories.includes(category) ? 'i-lucide-check' : 'i-lucide-plus'"
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
            <span class="text-xs text-zinc-500 tabular-nums">{{ selectedLots.length }} / {{ lotOptions.length }}</span>
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
                :class="selectedLots.includes(lot)
                  ? 'bg-sky-600 text-white ring-sky-600 dark:bg-sky-400 dark:text-sky-950 dark:ring-sky-400'
                  : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
                @click="toggleLot(lot)"
              >
                <UIcon
                  :name="selectedLots.includes(lot) ? 'i-lucide-check' : 'i-lucide-plus'"
                  class="h-3.5 w-3.5"
                />
                {{ lot }}
              </button>
            </div>
            <p
              v-if="visibleLotOptions.length === 0"
              class="px-2 py-4 text-center text-sm text-zinc-500"
            >
              {{ text.noLots }}
            </p>
          </div>
        </div>
      </div>
    </UCard>

    <UCard
      v-if="hasMSelection"
      class="dashboard-surface rounded-2xl"
      :ui="{ header: 'px-4 py-3 sm:px-4', body: 'px-4 py-4 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ text.mFilter }}
          </h2>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            :label="text.reset"
            :disabled="selectedTechs.length === 0 && techSearch.length === 0"
            @click="clearMFilters"
          />
        </div>
      </template>

      <div class="space-y-2">
        <div class="flex items-center justify-between gap-2">
          <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            tech_nm
          </p>
          <span class="text-xs text-zinc-500 tabular-nums">{{ selectedTechs.length }} / {{ techOptions.length }}</span>
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
            :class="selectedTechs.includes(tech)
              ? 'bg-violet-600 text-white ring-violet-600 dark:bg-violet-400 dark:text-violet-950 dark:ring-violet-400'
              : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
            @click="toggleTech(tech)"
          >
            <UIcon
              :name="selectedTechs.includes(tech) ? 'i-lucide-check' : 'i-lucide-plus'"
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
        sticky="header"
      >
        <template #source-cell="{ row }">
          <UBadge
            :label="getSourceLabel(row.original.source)"
            size="xs"
            :color="row.original.source === 'r3_device_grp' ? 'success' : 'info'"
            variant="subtle"
          />
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
</template>

<style scoped>
.font-mono-ids :deep(td) {
  font-size: 12.5px;
}

.font-mono-ids :deep(td:nth-child(2)),
.font-mono-ids :deep(td:nth-child(4)),
.font-mono-ids :deep(td:nth-child(5)),
.font-mono-ids :deep(td:nth-child(6)),
.font-mono-ids :deep(td:nth-child(8)),
.font-mono-ids :deep(td:nth-child(9)) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
