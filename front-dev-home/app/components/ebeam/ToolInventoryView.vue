<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ColumnFiltersState, SortingState } from '@tanstack/vue-table'
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/mock-data/sem-list/sem-list'

const props = withDefaults(defineProps<{
  fab?: Fab
  subtitle: string
  title: string
  toolType: ToolType
}>(), {
  fab: 'all'
})

const { fetchSemList, filterRows } = useSemListApi()

const asyncKey = `sem-list:${props.toolType}:${props.fab}`

const { data } = await useAsyncData(asyncKey, async () => {
  const allRows = await fetchSemList()
  const rows = filterRows(allRows, props.toolType, props.fab)
  const facSummaries = props.fab === 'all' ? summarizeRowsByFacId(rows) : []

  return {
    rows,
    facSummaries
  }
})

const rows = computed(() => data.value?.rows ?? [])
const facSummaries = computed(() => data.value?.facSummaries ?? [])
const onlineCount = computed(() => rows.value.filter(row => row.available === 'On').length)
const offlineCount = computed(() => rows.value.filter(row => row.available === 'Off').length)
const facCount = computed(() => new Set(rows.value.map(row => row.fac_id)).size)

const defaultSortPreset = 'fab_name:asc'

const globalFilter = ref('')
const columnFilters = ref<ColumnFiltersState>([])
const sorting = ref<SortingState>([
  {
    id: 'fab_name',
    desc: false
  }
])

const setColumnFilter = (columnId: keyof SemListRow, value: string) => {
  const nextFilters = columnFilters.value.filter(filter => filter.id !== columnId)

  if (value !== 'all') {
    nextFilters.push({
      id: columnId,
      value
    })
  }

  columnFilters.value = nextFilters
}

const getColumnFilter = (columnId: keyof SemListRow) => {
  const filter = columnFilters.value.find(entry => entry.id === columnId)

  return typeof filter?.value === 'string' ? filter.value : 'all'
}

const availabilityFilter = computed({
  get: () => getColumnFilter('available'),
  set: (value: string) => setColumnFilter('available', value)
})

const modelFilter = computed({
  get: () => getColumnFilter('eqp_model_cd'),
  set: (value: string) => setColumnFilter('eqp_model_cd', value)
})

const fabNameFilter = computed({
  get: () => getColumnFilter('fab_name'),
  set: (value: string) => setColumnFilter('fab_name', value)
})

const sortPreset = computed({
  get: () => {
    const currentSort = sorting.value[0]

    if (!currentSort) {
      return defaultSortPreset
    }

    return `${currentSort.id}:${currentSort.desc ? 'desc' : 'asc'}`
  },
  set: (value: string) => {
    const [columnId = 'fab_name', direction = 'asc'] = value.split(':')

    sorting.value = [
      {
        id: columnId,
        desc: direction === 'desc'
      }
    ]
  }
})

const availabilityFilterOptions = [
  { label: 'All Statuses', value: 'all' },
  { label: 'On', value: 'On' },
  { label: 'Off', value: 'Off' }
]

const modelFilterOptions = computed(() => [
  { label: 'All Models', value: 'all' },
  ...Array.from(new Set(rows.value.map(row => row.eqp_model_cd)))
    .sort((left, right) => left.localeCompare(right))
    .map(model => ({
      label: model,
      value: model
    }))
])

const fabNameFilterOptions = computed(() => [
  { label: 'All Fabs', value: 'all' },
  ...Array.from(new Set(rows.value.map(row => row.fab_name)))
    .sort((left, right) => left.localeCompare(right))
    .map(fabName => ({
      label: fabName,
      value: fabName
    }))
])

const showFabNameFilter = computed(() => fabNameFilterOptions.value.length > 2)

const sortOptions = [
  { label: 'Fab (A-Z)', value: 'fab_name:asc' },
  { label: 'Fab (Z-A)', value: 'fab_name:desc' },
  { label: 'Equipment ID (A-Z)', value: 'eqp_id:asc' },
  { label: 'Equipment ID (Z-A)', value: 'eqp_id:desc' },
  { label: 'Model (A-Z)', value: 'eqp_model_cd:asc' },
  { label: 'Model (Z-A)', value: 'eqp_model_cd:desc' },
  { label: 'IP Address (A-Z)', value: 'eqp_ip:asc' },
  { label: 'IP Address (Z-A)', value: 'eqp_ip:desc' },
  { label: 'Version (Low to High)', value: 'version:asc' },
  { label: 'Version (High to Low)', value: 'version:desc' },
  { label: 'Status (Off first)', value: 'available:asc' },
  { label: 'Status (On first)', value: 'available:desc' }
]

const filteredRowCount = computed(() => {
  const searchTerm = globalFilter.value.trim().toLowerCase()
  const selectedAvailability = availabilityFilter.value
  const selectedModel = modelFilter.value
  const selectedFabName = fabNameFilter.value

  return rows.value.filter((row) => {
    const matchesSearch = searchTerm.length === 0 || [
      row.fac_id,
      row.fab_name,
      row.eqp_id,
      row.eqp_model_cd,
      row.vendor_nm,
      row.eqp_ip,
      String(row.version),
      row.available
    ].some(value => value.toLowerCase().includes(searchTerm))

    const matchesAvailability = selectedAvailability === 'all' || row.available === selectedAvailability
    const matchesModel = selectedModel === 'all' || row.eqp_model_cd === selectedModel
    const matchesFabName = selectedFabName === 'all' || row.fab_name === selectedFabName

    return matchesSearch && matchesAvailability && matchesModel && matchesFabName
  }).length
})

const hasActiveTableControls = computed(() => {
  return globalFilter.value.length > 0 || columnFilters.value.length > 0 || sortPreset.value !== defaultSortPreset
})

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50'
  }
}

const columns: TableColumn<SemListRow>[] = [
  {
    accessorKey: 'fac_id',
    header: 'Fac'
  },
  {
    accessorKey: 'fab_name',
    header: 'Fab',
    filterFn: 'equalsString'
  },
  {
    accessorKey: 'eqp_id',
    header: 'Equipment ID'
  },
  {
    accessorKey: 'eqp_model_cd',
    header: 'Model',
    filterFn: 'equalsString'
  },
  {
    accessorKey: 'vendor_nm',
    header: 'Vendor'
  },
  {
    accessorKey: 'eqp_ip',
    header: 'IP Address'
  },
  {
    accessorKey: 'version',
    header: 'Version',
    sortingFn: 'basic'
  },
  {
    accessorKey: 'available',
    header: 'Available',
    filterFn: 'equalsString'
  }
]

const resetTableControls = () => {
  globalFilter.value = ''
  columnFilters.value = []
  sorting.value = [
    {
      id: 'fab_name',
      desc: false
    }
  ]
}

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') {
    return 'i-lucide-arrow-up-narrow-wide'
  }

  if (direction === 'desc') {
    return 'i-lucide-arrow-down-wide-narrow'
  }

  return 'i-lucide-arrow-up-down'
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">
        {{ title }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ subtitle }}
      </p>
    </div>

    <div class="grid gap-4 md:grid-cols-4">
      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {{ rows.length }}
          </div>
          <div class="text-sm text-gray-500">
            Total Tools
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-800 dark:text-zinc-200">
            {{ onlineCount }}
          </div>
          <div class="text-sm text-gray-500">
            Online
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-700 dark:text-zinc-300">
            {{ offlineCount }}
          </div>
          <div class="text-sm text-gray-500">
            Offline
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-600 dark:text-zinc-400">
            {{ facCount }}
          </div>
          <div class="text-sm text-gray-500">
            Fabs
          </div>
        </div>
      </UCard>
    </div>

    <template v-if="props.fab === 'all' && facSummaries.length > 0">
      <div>
        <h2 class="text-lg font-semibold mb-4">
          Fab Breakdown
        </h2>
        <div class="grid gap-4 md:grid-cols-3">
          <UCard
            v-for="summary in facSummaries"
            :key="summary.fac_id"
            class="dashboard-surface rounded-2xl"
          >
            <div class="flex items-center justify-between mb-3">
              <h3 class="font-semibold">
                {{ summary.fac_id }}
              </h3>
              <UBadge
                :label="`${summary.online}/${summary.total} online`"
                color="neutral"
                variant="subtle"
              />
            </div>

            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Total Tools
                </span>
                <span class="font-medium">
                  {{ summary.total }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Online
                </span>
                <span class="font-medium">
                  {{ summary.online }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Offline
                </span>
                <span class="font-medium">
                  {{ summary.offline }}
                </span>
              </div>
            </div>

            <div class="mt-4">
              <NuxtLink
                :to="`/ebeam/${toolType}/${summary.fac_id.toLowerCase()}`"
                class="text-sm font-medium text-zinc-700 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100"
              >
                View Details ->
              </NuxtLink>
            </div>
          </UCard>
        </div>
      </div>
    </template>

    <div>
      <h2 class="text-lg font-semibold mb-4">
        Tool Inventory
      </h2>
      <UCard class="dashboard-surface rounded-2xl">
        <div class="space-y-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div class="flex flex-1 flex-col gap-3 md:flex-row md:flex-wrap">
              <UInput
                v-model="globalFilter"
                class="w-full md:min-w-[18rem] md:flex-1"
                icon="i-lucide-search"
                color="neutral"
                variant="subtle"
                placeholder="Search tool inventory"
              />

              <USelect
                v-model="availabilityFilter"
                class="w-full md:w-48"
                color="neutral"
                variant="subtle"
                :items="availabilityFilterOptions"
              />

              <USelect
                v-model="modelFilter"
                class="w-full md:w-52"
                color="neutral"
                variant="subtle"
                :items="modelFilterOptions"
              />

              <USelect
                v-if="showFabNameFilter"
                v-model="fabNameFilter"
                class="w-full md:w-40"
                color="neutral"
                variant="subtle"
                :items="fabNameFilterOptions"
              />

              <USelect
                v-model="sortPreset"
                class="w-full md:w-56"
                color="neutral"
                variant="subtle"
                :items="sortOptions"
              />
            </div>

            <div class="flex items-center justify-between gap-3 lg:justify-end">
              <p class="text-sm text-gray-500">
                {{ filteredRowCount }} of {{ rows.length }} tools
              </p>

              <UButton
                color="neutral"
                variant="outline"
                label="Reset"
                :disabled="!hasActiveTableControls"
                @click="resetTableControls"
              />
            </div>
          </div>

          <UTable
            v-model:global-filter="globalFilter"
            v-model:column-filters="columnFilters"
            v-model:sorting="sorting"
            class="max-h-[36rem]"
            :columns="columns"
            :data="rows"
            :empty="`No tools match the current search or filters.`"
            :meta="tableMeta"
            :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
            sticky="header"
          >
            <template #fac_id-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Fac
              </UButton>
            </template>

            <template #fab_name-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Fab
              </UButton>
            </template>

            <template #eqp_id-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Equipment ID
              </UButton>
            </template>

            <template #eqp_model_cd-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Model
              </UButton>
            </template>

            <template #vendor_nm-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Vendor
              </UButton>
            </template>

            <template #eqp_ip-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                IP Address
              </UButton>
            </template>

            <template #version-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Version
              </UButton>
            </template>

            <template #available-header="{ column }">
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="-mx-2"
                :trailing-icon="getSortIcon(column.getIsSorted())"
                @click="column.toggleSorting(column.getIsSorted() === 'asc')"
              >
                Available
              </UButton>
            </template>

            <template #available-cell="{ row }">
              <UBadge
                :label="row.original.available"
                :color="row.original.available === 'On' ? 'success' : 'neutral'"
                variant="subtle"
              />
            </template>
          </UTable>
        </div>
      </UCard>
    </div>
  </div>
</template>
