<script setup lang="ts">
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'

const props = defineProps<{
  fab: Fab
  subtitle: string
  title: string
  toolType: ToolType
}>()

const { filterRows } = useSemListApi()
const { setSelectedTool } = useNavigation()

const { data: allRows } = await useSemList()
const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fab))

const defaultSortPreset = 'eqp_id:asc'

const globalFilter = ref('')
const availabilityFilter = ref<'all' | 'On' | 'Off'>('all')
const modelFilter = ref<string>('all')
const sortPresetRaw = ref(defaultSortPreset)

const sortPreset = computed({
  get: () => sortPresetRaw.value,
  set: (value: string) => {
    sortPresetRaw.value = value
  }
})

const toggleAvailabilityFilter = (target: 'On' | 'Off') => {
  availabilityFilter.value = availabilityFilter.value === target ? 'all' : target
}

type StatusCard = {
  status: 'On' | 'Off'
  label: string
  countBg: string
  countFg: string
  ringClass: string
  focusRingClass: string
  subline: (count: number, total: number) => string
}

const statusCards: StatusCard[] = [
  {
    status: 'On',
    label: 'Available',
    countBg: 'var(--sk-ok-soft)',
    countFg: 'var(--sk-ok)',
    ringClass: 'ring-(--sk-ok)',
    focusRingClass: 'focus-visible:ring-(--sk-ok)',
    subline: (count, total) => `${count}/${total} ready to dispatch`
  },
  {
    status: 'Off',
    label: 'Offline',
    countBg: 'var(--sk-bad-soft)',
    countFg: 'var(--sk-bad)',
    ringClass: 'ring-(--sk-bad)',
    focusRingClass: 'focus-visible:ring-(--sk-bad)',
    subline: count => count === 0 ? 'all tools available' : 'needs attention'
  }
]

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

const sortedFilteredRows = computed(() => {
  const [columnIdRaw = 'eqp_id', direction = 'asc'] = sortPreset.value.split(':')
  const columnId = columnIdRaw as keyof SemListRow
  const sign = direction === 'desc' ? -1 : 1
  const out = [...filteredRows.value]

  out.sort((left, right) => {
    const leftValue = left[columnId]
    const rightValue = right[columnId]

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * sign
    }

    return sortCollator.compare(String(leftValue), String(rightValue)) * sign
  })

  return out
})

const filteredRowCount = computed(() => filteredRows.value.length)

const segmentCounts = computed(() => {
  // Counts respect search + model filter, so the segmented control reflects what
  // the user would see if they clicked through. Status itself isn't applied here.
  const searchTerm = globalFilter.value.trim().toLowerCase()
  const selectedModel = modelFilter.value

  let all = 0
  let on = 0
  let off = 0

  for (const row of rows.value) {
    const matchesSearch = searchTerm.length === 0 || [
      row.fac_id, row.fab_name, row.eqp_id, row.eqp_model_cd,
      row.vendor_nm, row.eqp_ip, String(row.version), row.available
    ].some(value => value.toLowerCase().includes(searchTerm))
    const matchesModel = selectedModel === 'all' || row.eqp_model_cd === selectedModel

    if (!matchesSearch || !matchesModel) continue

    all++
    if (row.available === 'On') on++
    else if (row.available === 'Off') off++
  }

  return { all, On: on, Off: off }
})

type GroupTone = 'ok' | 'off'
type Group = { tone: GroupTone, label: string, rows: SemListRow[] }

const groupedRows = computed<Group[]>(() => {
  const off = sortedFilteredRows.value.filter(r => r.available === 'Off')
  const on = sortedFilteredRows.value.filter(r => r.available === 'On')

  const groups: Group[] = []
  // Offline first — the only group with implied action.
  if (off.length > 0) groups.push({ tone: 'off', label: 'Offline', rows: off })
  if (on.length > 0) groups.push({ tone: 'ok', label: 'Available', rows: on })
  return groups
})

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return `${props.toolType}-${props.fab.toLowerCase()}-tool-inventory-${today}.csv`
})

const hasActiveTableControls = computed(() => {
  return globalFilter.value.length > 0
    || availabilityFilter.value !== 'all'
    || modelFilter.value !== 'all'
    || sortPreset.value !== defaultSortPreset
})

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

const resetTableControls = () => {
  globalFilter.value = ''
  availabilityFilter.value = 'all'
  modelFilter.value = 'all'
  sortPresetRaw.value = defaultSortPreset
}

const escapeCsvValue = (value: string | number) => {
  const normalized = String(value).replace(/"/g, '""')
  return `"${normalized}"`
}

const downloadTableCsv = () => {
  if (!import.meta.client || sortedFilteredRows.value.length === 0) return

  const headerRow = csvColumns.map(column => escapeCsvValue(column.header)).join(',')
  const bodyRows = sortedFilteredRows.value.map(row => (
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

<template>
  <div class="space-y-3">
    <EbeamFeatureHeader
      :subtitle="subtitle"
      :title="title"
    />

    <slot name="below-title" />

    <!-- Overview strip — also the availability filter (click a card to filter the table) -->
    <div
      class="grid grid-cols-2 gap-2.5"
      role="radiogroup"
      aria-label="Filter by availability"
    >
      <button
        v-for="card in statusCards"
        :key="card.status"
        type="button"
        role="radio"
        :aria-checked="availabilityFilter === card.status"
        class="dashboard-surface rounded-2xl px-4 py-3.5 flex items-center gap-3.5 text-left transition cursor-pointer hover:brightness-[0.99] focus:outline-none focus-visible:ring-2"
        :class="[
          card.focusRingClass,
          availabilityFilter === card.status ? `ring-2 ${card.ringClass} shadow-sm` : 'ring-1 ring-transparent'
        ]"
        @click="toggleAvailabilityFilter(card.status)"
      >
        <span
          class="inline-flex items-center justify-center w-9 h-9 rounded-[10px] font-mono font-bold text-[17px] tabular-nums"
          :style="{ background: card.countBg, color: card.countFg }"
        >{{ segmentCounts[card.status] }}</span>
        <div class="min-w-0">
          <p class="text-[13px] font-semibold leading-tight">
            {{ card.label }}
          </p>
          <p class="text-[11.5px] text-zinc-500 mt-0.5">
            {{ card.subline(segmentCounts[card.status], segmentCounts.all) }}
          </p>
        </div>
      </button>
    </div>

    <!-- Tool Inventory grouped card -->
    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-baseline gap-2">
            <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Tool Inventory
            </h2>
            <span class="text-[11.5px] text-zinc-500">grouped by status</span>
          </div>
          <p class="text-xs text-zinc-500 tabular-nums">
            {{ filteredRowCount }} of {{ rows.length }} tools
          </p>
        </div>
      </template>

      <!-- Toolbar -->
      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-zinc-200/70 dark:border-zinc-800/70">
        <UInput
          v-model="globalFilter"
          class="flex-1 min-w-56"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search by Equipment ID, Model, IP…"
        />

        <USelect
          v-model="modelFilter"
          class="w-44"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="modelFilterOptions"
        />

        <USelect
          v-model="sortPreset"
          class="w-52"
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
          variant="ghost"
          icon="i-lucide-rotate-ccw"
          label="Reset"
          :disabled="!hasActiveTableControls"
          @click="resetTableControls"
        />
      </div>

      <!-- Empty state -->
      <p
        v-if="groupedRows.length === 0"
        class="px-6 py-12 text-center text-sm text-zinc-500"
      >
        No tools match the current search or filters.
      </p>

      <!-- Grouped tables -->
      <div
        v-for="group in groupedRows"
        :key="group.label"
        class="inv-group"
      >
        <!-- Group band -->
        <div
          class="flex items-center gap-2.5 px-4.5 py-2.5 border-t border-b text-[11px] tracking-[0.06em] uppercase font-bold"
          :class="'inv-group__band'"
          :style="{
            background: 'var(--sk-muted-surface)',
            borderColor: 'var(--sk-border-soft)'
          }"
        >
          <span
            class="inline-block w-2 h-2 rounded-full"
            :style="{ background: group.tone === 'off' ? 'var(--sk-bad)' : 'var(--sk-ok)' }"
          />
          <span class="text-(--sk-ink)">{{ group.label }}</span>
          <span class="font-medium tracking-normal normal-case text-zinc-500 tabular-nums">
            {{ group.rows.length }} {{ group.rows.length === 1 ? 'tool' : 'tools' }}
          </span>
        </div>

        <table class="w-full table-fixed border-collapse">
          <colgroup>
            <col style="width: 27%;">
            <col style="width: 19%;">
            <col style="width: 16%;">
            <col style="width: 27%;">
            <col style="width: 11%;">
          </colgroup>
          <tbody>
            <tr
              v-for="row in group.rows"
              :key="row.eqp_id"
              class="border-b"
              :style="{
                background: group.tone === 'off' ? 'oklch(0.58 0.18 28 / 0.06)' : 'transparent',
                borderColor: 'var(--sk-border-soft)'
              }"
            >
              <td class="inv-cell">
                <div class="flex items-center gap-2">
                  <span class="font-mono font-bold text-[14.5px] text-(--sk-ink) tracking-tight">
                    {{ row.eqp_id }}
                  </span>
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="subtle"
                    trailing-icon="i-lucide-arrow-right"
                    label="H/W"
                    :aria-label="`Open hardware view for ${row.eqp_id}`"
                    @click="goToHardware(row.eqp_id)"
                  />
                </div>
              </td>
              <td class="inv-cell">
                <span class="text-[12.5px] font-medium text-(--sk-ink)">
                  {{ row.eqp_model_cd }}
                </span>
              </td>
              <td class="inv-cell">
                <span class="text-[11.5px] text-zinc-500 capitalize">
                  {{ row.vendor_nm.toLowerCase() }}
                </span>
              </td>
              <td class="inv-cell">
                <span class="font-mono text-[11.5px] text-(--sk-ink-muted) tabular-nums">
                  {{ row.eqp_ip }}
                </span>
              </td>
              <td class="inv-cell">
                <span class="font-mono text-[11.5px] text-(--sk-ink-muted) tabular-nums">
                  v{{ row.version }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </div>
</template>

<style scoped>
.inv-cell {
  padding: 11px 18px;
  vertical-align: middle;
}
</style>
