<template>
  <div class="flex flex-col gap-3 h-full min-h-0">
    <EbeamMetaBar
      :eyebrow="eyebrow"
      :title="title"
      :subtitle="subtitle"
      :cadence="cadence"
      :stats="metaStats"
      interactive-stats
      stats-label="가용성으로 필터"
      @select-stat="onSelectStat"
    >
      <template #toggle>
        <EbeamEquipmentStatusSubTabs />
      </template>
    </EbeamMetaBar>

    <UCard
      class="dashboard-surface rounded-2xl flex flex-col flex-1 min-h-0"
      :ui="{ body: 'p-0 sm:p-0 flex flex-1 flex-col min-h-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Tool Inventory
          </h2>
          <p class="text-xs text-(--sk-ink-muted) tabular-nums">
            {{ filteredRows.length }} of {{ rows.length }} tools
          </p>
        </div>
      </template>

      <!-- Toolbar -->
      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-zinc-200/70 dark:border-zinc-800/70">
        <UInput
          v-model="globalFilter"
          class="flex-1 min-w-56"
          size="sm"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search by Equipment ID, Model, IP…"
        />

        <USelect
          v-model="modelFilter"
          class="w-44"
          size="sm"
          color="neutral"
          variant="subtle"
          :items="modelFilterOptions"
        />

        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          label="CSV 다운로드"
          :disabled="filteredRows.length === 0"
          @click="downloadTableCsv"
        />

        <UButton
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-lucide-rotate-ccw"
          label="Reset"
          :disabled="!hasActiveTableControls"
          @click="resetTableControls"
        />
      </div>

      <UTable
        v-model:sorting="sorting"
        class="flex-1 min-h-0 font-mono-ids"
        :columns="columns"
        :data="filteredRows"
        :empty="`No tools match the current search or filters.`"
        :meta="tableMeta"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false, manualSorting: true }"
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
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #available-cell="{ row }">
          <span
            class="inline-flex items-center gap-1.5 text-[12px] font-semibold"
            :style="{ color: row.original.available === 'Off' ? 'var(--sk-bad)' : 'var(--sk-ok)' }"
          >
            <span
              class="inline-block w-1.5 h-1.5 rounded-full"
              :style="{ background: row.original.available === 'Off' ? 'var(--sk-bad)' : 'var(--sk-ok)' }"
            />
            {{ row.original.available === 'Off' ? 'Offline' : 'Available' }}
          </span>
        </template>

        <template #eqp_id-cell="{ row }">
          <div class="flex items-center gap-3">
            <span class="font-mono font-bold text-[13px] text-(--sk-ink) tracking-tight">
              {{ row.original.eqp_id }}
            </span>
            <UButton
              size="xs"
              color="neutral"
              variant="subtle"
              trailing-icon="i-lucide-arrow-right"
              label="H/W 상태"
              :aria-label="`Open hardware view for ${row.original.eqp_id}`"
              @click="goToHardware(row.original.eqp_id)"
            />
          </div>
        </template>

        <template #eqp_model_cd-cell="{ row }">
          <span class="text-[12.5px] font-medium text-(--sk-ink)">{{ row.original.eqp_model_cd }}</span>
        </template>
        <template #vendor_nm-cell="{ row }">
          <span class="text-[11.5px] text-(--sk-ink) capitalize">{{ row.original.vendor_nm.toLowerCase() }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[11.5px] text-(--sk-ink)">{{ row.original.eqp_ip }}</span>
        </template>
        <template #version-cell="{ row }">
          <span class="font-mono tabular-nums text-[11.5px] text-(--sk-ink)">v{{ row.original.version }}</span>
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'
import type { MetaBarStat } from './MetaBar.vue'

const props = defineProps<{
  fab: Fab
  eyebrow?: string
  cadence?: string
  subtitle: string
  title: string
  toolType: ToolType
}>()

const { filterRows } = useSemListApi()
const { setSelectedTool } = useNavigation()

const { data: allRows } = await useSemList()
const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fab))

const globalFilter = ref('')
const availabilityFilter = ref<'all' | 'On' | 'Off'>('all')
const modelFilter = ref<string>('all')

// Available-first by default ('On' sorts above 'Off'), but every column header
// is click-sortable so engineers can re-order however they like.
const defaultSort = { id: 'available', desc: true }
// Seed (and reset) with a fresh copy so the baseline object can never be
// mutated in place by the table's sorting state.
const sorting = ref<SortingState>([{ ...defaultSort }])

const toggleAvailabilityFilter = (target: 'On' | 'Off') => {
  availabilityFilter.value = availabilityFilter.value === target ? 'all' : target
}

const goToHardware = (eqpId: string) => {
  setSelectedTool(eqpId)
  return navigateTo(`/ebeam/${props.toolType}/${props.fab.toLowerCase()}/hardware`)
}

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

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

// One source of truth per filter rule, reused by both the table and the
// meta-bar segment counts so the two can never drift apart.
const searchableFields = (row: SemListRow) => [
  row.fac_id, row.fab_name, row.eqp_id, row.eqp_model_cd,
  row.vendor_nm, row.eqp_ip, String(row.version), row.available
]

const matchesSearch = (row: SemListRow) => {
  const term = globalFilter.value.trim().toLowerCase()
  return term.length === 0 || searchableFields(row).some(value => value.toLowerCase().includes(term))
}

const matchesModel = (row: SemListRow) =>
  modelFilter.value === 'all' || row.eqp_model_cd === modelFilter.value

const matchesAvailability = (row: SemListRow) =>
  availabilityFilter.value === 'all' || row.available === availabilityFilter.value

const compareRows = (left: SemListRow, right: SemListRow, key: keyof SemListRow) => {
  const leftValue = left[key]
  const rightValue = right[key]

  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    return leftValue - rightValue
  }

  return sortCollator.compare(String(leftValue), String(rightValue))
}

const filteredRows = computed(() => {
  const matched = rows.value.filter(row => matchesSearch(row) && matchesModel(row) && matchesAvailability(row))

  const currentSort = sorting.value[0]
  if (!currentSort) return matched

  const key = currentSort.id as keyof SemListRow
  const direction = currentSort.desc ? -1 : 1

  return [...matched].sort((a, b) => {
    const result = compareRows(a, b, key)
    if (result !== 0) return result * direction
    // Stable secondary order so rows within a status (or model) stay readable.
    return sortCollator.compare(a.eqp_id, b.eqp_id)
  })
})

const segmentCounts = computed(() => {
  // Counts respect search + model filter, so the segmented control reflects what
  // the user would see if they clicked through. Status itself isn't applied here.
  let on = 0
  let off = 0

  for (const row of rows.value) {
    if (!matchesSearch(row) || !matchesModel(row)) continue
    if (row.available === 'On') on++
    else if (row.available === 'Off') off++
  }

  return { On: on, Off: off }
})

// Summary stats for the meta bar — these double as the availability filter
// (click a segment to toggle the table filter, like the old overview cards did).
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'On', value: segmentCounts.value.On, label: 'Available', tone: 'ok', active: availabilityFilter.value === 'On' },
  { key: 'Off', value: segmentCounts.value.Off, label: 'Offline', tone: 'bad', active: availabilityFilter.value === 'Off' }
])

const onSelectStat = (key: string) => {
  if (key === 'On' || key === 'Off') toggleAvailabilityFilter(key)
}

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return `${props.toolType}-${props.fab.toLowerCase()}-tool-inventory-${today}.csv`
})

const hasActiveTableControls = computed(() => {
  const currentSort = sorting.value[0]
  return globalFilter.value.length > 0
    || availabilityFilter.value !== 'all'
    || modelFilter.value !== 'all'
    || currentSort?.id !== defaultSort.id
    || currentSort?.desc !== defaultSort.desc
})

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

type ColumnConfig = { id: keyof SemListRow, header: string, size: number }

const columnConfigs: ColumnConfig[] = [
  { id: 'available', header: 'Status', size: 120 },
  { id: 'eqp_id', header: 'Equipment ID', size: 220 },
  { id: 'eqp_model_cd', header: 'Model', size: 140 },
  { id: 'vendor_nm', header: 'Vendor', size: 110 },
  { id: 'eqp_ip', header: 'IP Address', size: 160 },
  { id: 'version', header: 'Version', size: 90 }
]

const columns: TableColumn<SemListRow>[] = columnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))

const sortableHeaders = columnConfigs.map(column => ({
  id: column.id,
  label: column.header
}))

const resetTableControls = () => {
  globalFilter.value = ''
  availabilityFilter.value = 'all'
  modelFilter.value = 'all'
  sorting.value = [{ ...defaultSort }]
}

// CSV columns — keep all 8 fields even though several have been dropped from the UI.
// Analysts pull this into Excel and want the full record.
type CsvColumn = { id: keyof SemListRow, header: string }
const csvColumns: CsvColumn[] = [
  { id: 'fac_id', header: 'Fac' },
  { id: 'fab_name', header: 'Fab' },
  { id: 'eqp_id', header: 'Equipment ID' },
  { id: 'eqp_model_cd', header: 'Model' },
  { id: 'vendor_nm', header: 'Vendor' },
  { id: 'eqp_ip', header: 'IP Address' },
  { id: 'version', header: 'Version' },
  { id: 'available', header: 'Available' }
]

const escapeCsvValue = (value: string | number) => {
  const normalized = String(value).replace(/"/g, '""')
  return `"${normalized}"`
}

const downloadTableCsv = () => {
  if (!import.meta.client || filteredRows.value.length === 0) return

  const headerRow = csvColumns.map(column => escapeCsvValue(column.header)).join(',')
  const bodyRows = filteredRows.value.map(row => (
    csvColumns
      .map(column => escapeCsvValue(row[column.id]))
      .join(',')
  ))

  const csvContent = ['﻿' + headerRow, ...bodyRows].join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = exportFileName.value
  link.click()

  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
