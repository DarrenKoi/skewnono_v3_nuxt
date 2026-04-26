<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ColumnFiltersState, SortingState } from '@tanstack/vue-table'
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'

const props = defineProps<{
  fab: Fab
  subtitle: string
  title: string
  toolType: ToolType
}>()

const { filterRows } = useSemListApi()

const { data: allRows } = await useSemList()
const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fab))

const rowSummary = computed(() => {
  let online = 0
  let offline = 0

  for (const row of rows.value ?? []) {
    if (row.available === 'On') online++
    else if (row.available === 'Off') offline++
  }

  return { online, offline }
})

const defaultSortPreset = 'eqp_id:asc'

const globalFilter = ref('')
const columnFilters = ref<ColumnFiltersState>([])
const sorting = ref<SortingState>([
  {
    id: 'eqp_id',
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

const sortPreset = computed({
  get: () => {
    const currentSort = sorting.value[0]

    if (!currentSort) {
      return defaultSortPreset
    }

    return `${currentSort.id}:${currentSort.desc ? 'desc' : 'asc'}`
  },
  set: (value: string) => {
    const [columnId = 'eqp_id', direction = 'asc'] = value.split(':')

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

const sortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const sortOptions = [
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

const matchesActiveFilters = (row: SemListRow) => {
  const searchTerm = globalFilter.value.trim().toLowerCase()
  const selectedAvailability = availabilityFilter.value
  const selectedModel = modelFilter.value

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

  return matchesSearch && matchesAvailability && matchesModel
}

const filteredRows = computed(() => rows.value.filter(matchesActiveFilters))

const exportRows = computed(() => {
  const currentSort = sorting.value[0]
  const sortedRows = [...filteredRows.value]

  if (!currentSort) {
    return sortedRows
  }

  const columnId = currentSort.id as keyof SemListRow
  const direction = currentSort.desc ? -1 : 1

  return sortedRows.sort((left, right) => {
    const leftValue = left[columnId]
    const rightValue = right[columnId]

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * direction
    }

    return sortCollator.compare(String(leftValue), String(rightValue)) * direction
  })
})

const filteredRowCount = computed(() => filteredRows.value.length)

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)

  return `${props.toolType}-${props.fab.toLowerCase()}-tool-inventory-${today}.csv`
})

const hasActiveTableControls = computed(() => {
  return globalFilter.value.length > 0 || columnFilters.value.length > 0 || sortPreset.value !== defaultSortPreset
})

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

type InventoryColumnConfig = {
  id: keyof SemListRow
  header: string
  size: number
  filterFn?: 'equalsString'
  sortingFn?: 'basic'
}

const columnConfigs: InventoryColumnConfig[] = [
  { id: 'fac_id', header: 'Fac', size: 56 },
  { id: 'fab_name', header: 'Fab', size: 64, filterFn: 'equalsString' },
  { id: 'eqp_id', header: 'Equipment ID', size: 130 },
  { id: 'eqp_model_cd', header: 'Model', size: 140, filterFn: 'equalsString' },
  { id: 'vendor_nm', header: 'Vendor', size: 86 },
  { id: 'eqp_ip', header: 'IP Address', size: 150 },
  { id: 'version', header: 'Version', size: 76, sortingFn: 'basic' },
  { id: 'available', header: 'Available', size: 100, filterFn: 'equalsString' }
]

const columns: TableColumn<SemListRow>[] = columnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))

const sortableHeaders = columnConfigs.map(column => ({
  id: column.id,
  label: column.header
}))

const monoColumns: (keyof SemListRow)[] = ['eqp_id', 'eqp_model_cd', 'eqp_ip', 'version']
const mutedColumns: (keyof SemListRow)[] = ['fac_id', 'fab_name']

const statCells = computed(() => [
  { label: 'Total Tools', value: rows.value.length, tone: 'text-zinc-900 dark:text-zinc-100' },
  { label: 'Online', value: rowSummary.value.online, tone: 'text-(--sk-accent)' },
  { label: 'Offline', value: rowSummary.value.offline, tone: 'text-zinc-600 dark:text-zinc-400' }
])

const resetTableControls = () => {
  globalFilter.value = ''
  columnFilters.value = []
  sorting.value = [
    {
      id: 'eqp_id',
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

const escapeCsvValue = (value: string | number) => {
  const normalized = String(value).replace(/"/g, '""')
  return `"${normalized}"`
}

const downloadTableCsv = () => {
  if (!import.meta.client || exportRows.value.length === 0) {
    return
  }

  const headerRow = columnConfigs.map(column => escapeCsvValue(column.header)).join(',')
  const bodyRows = exportRows.value.map(row => (
    columnConfigs
      .map(column => escapeCsvValue(row[column.id]))
      .join(',')
  ))

  const csvContent = ['\uFEFF' + headerRow, ...bodyRows].join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = exportFileName.value
  link.click()

  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight">
          {{ title }}
        </h1>
        <p class="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          {{ subtitle }}
        </p>
      </div>

      <div class="dashboard-surface rounded-2xl flex overflow-hidden self-start md:self-auto">
        <div
          v-for="(cell, index) in statCells"
          :key="cell.label"
          class="px-5 py-2.5 flex flex-col gap-0.5 min-w-[92px]"
          :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }"
        >
          <span
            class="text-[22px] font-bold leading-none tabular-nums"
            :class="cell.tone"
          >{{ cell.value }}</span>
          <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
        </div>
      </div>
    </div>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Tool Inventory
          </h2>
          <p class="text-xs text-zinc-500 tabular-nums">
            {{ filteredRowCount }} of {{ rows.length }} tools
          </p>
        </div>
      </template>

      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-zinc-200/70 dark:border-zinc-800/70">
        <UInput
          v-model="globalFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search tool inventory"
        />

        <USelect
          v-model="availabilityFilter"
          class="w-[9rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="availabilityFilterOptions"
        />

        <USelect
          v-model="modelFilter"
          class="w-[11rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="modelFilterOptions"
        />

        <USelect
          v-model="sortPreset"
          class="w-[13rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="sortOptions"
        />

        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          label="CSV 다운로드"
          :disabled="filteredRowCount === 0"
          @click="downloadTableCsv"
        />

        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="Reset"
          :disabled="!hasActiveTableControls"
          @click="resetTableControls"
        />
      </div>

      <UTable
        v-model:sorting="sorting"
        class="max-h-[34rem] font-mono-ids"
        :columns="columns"
        :data="exportRows"
        :empty="`No tools match the current search or filters.`"
        :meta="tableMeta"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
        sticky="header"
      >
        <template
          v-for="head in sortableHeaders"
          :key="head.id"
          #[`${head.id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #available-cell="{ row }">
          <UBadge
            :label="row.original.available"
            size="xs"
            :color="row.original.available === 'On' ? 'success' : 'error'"
            variant="subtle"
          />
        </template>

        <template
          v-for="key in monoColumns"
          :key="key"
          #[`${key}-cell`]="{ row }"
        >
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original[key] }}</span>
        </template>

        <template
          v-for="key in mutedColumns"
          :key="key"
          #[`${key}-cell`]="{ row }"
        >
          <span class="text-zinc-500 font-medium">{{ row.original[key] }}</span>
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
