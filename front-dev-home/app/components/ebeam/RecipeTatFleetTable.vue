<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          장비 목록
        </h3>
        <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
        </span>
        <span class="sk-meta">
          {{ selected.length }} / {{ maxSelected }}대 선택
        </span>
      </div>
      <div class="flex items-center gap-2">
        <UInput
          v-model="search"
          size="xs"
          placeholder="eqp_id / model 검색…"
          icon="i-lucide-search"
          class="w-[14rem]"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="선택 해제"
          :disabled="selected.length === 0"
          @click="emit('update:selected', [])"
        />
      </div>
    </div>

    <UTable
      v-model:sorting="sorting"
      :columns="columns"
      :data="sortedRows"
      :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
      sticky="header"
      :ui="tableUi"
    >
      <template
        v-for="id in sortableColumnIds"
        :key="id"
        #[`${id}-header`]="{ column }"
      >
        <UTooltip :text="headerTooltip(id)">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ column.columnDef.header }}
          </UButton>
        </UTooltip>
      </template>

      <template #pick-cell="{ row }">
        <UCheckbox
          :model-value="selected.includes(row.original.eqp_id)"
          :disabled="!selected.includes(row.original.eqp_id) && selected.length >= maxSelected"
          @update:model-value="toggle(row.original.eqp_id)"
        />
      </template>

      <template #occupancy-cell="{ row }">
        {{ (row.original.occupancy * 100).toFixed(1) }}%
      </template>

      <template #tat_index-cell="{ row }">
        <span :class="row.original.tat_index === null ? 'text-(--sk-ink-muted)' : ''">
          {{ row.original.tat_index === null ? '—' : row.original.tat_index.toFixed(2) }}
        </span>
      </template>

      <template #signals-cell="{ row }">
        <div class="flex flex-wrap gap-1">
          <span
            v-for="signal in signalsFor(row.original)"
            :key="signal"
            class="inline-flex h-5 items-center rounded px-1.5 text-[10px] font-medium ring-1"
            :class="SIGNAL_META[signal].tone === 'warn'
              ? 'bg-(--sk-warn-soft) text-(--sk-warn) ring-(--sk-warn-border)'
              : 'bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-(--sk-border-soft)'"
          >
            {{ SIGNAL_META[signal].label }}
          </span>
        </div>
      </template>
    </UTable>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import {
  formatSecondsAsDuration,
  type RecipeTatEquipmentRow
} from '~/composables/useRecipeTatApi'
import {
  equipmentSignals,
  SIGNAL_META,
  type FleetPercentiles
} from '~/utils/equipmentSignals'

const props = defineProps<{
  rows: RecipeTatEquipmentRow[]
  percentiles: FleetPercentiles
  selected: string[]
  maxSelected: number
}>()

const emit = defineEmits<{ 'update:selected': [string[]] }>()

const search = ref('')

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(row =>
    row.eqp_id.toLowerCase().includes(q)
    || row.eqp_model_cd.toLowerCase().includes(q)
    || row.fab_name.toLowerCase().includes(q))
})

const sortableColumnIds = [
  'exec_count', 'total_meastime', 'occupancy', 'avg_meastime', 'recipe_count', 'tat_index'
] as const
type SortableColumnId = typeof sortableColumnIds[number]

// 점유율은 측정 시간 기준이라 로딩·대기·PM이 빠져 있고, MES 가동률보다
// 낮게 읽힙니다. 헤더에 툴팁으로 못 박지 않으면 사용자가 62%를 보고
// 장비가 놀고 있다고 오해합니다.
const OCCUPANCY_HEADER_TOOLTIP
  = '측정 시간 기준입니다. 로딩·대기·PM이 빠져 있어 MES 가동률보다 낮게 읽힙니다.'

const headerTooltip = (id: SortableColumnId) =>
  id === 'occupancy' ? OCCUPANCY_HEADER_TOOLTIP : undefined

const sorting = ref<SortingState>([{ id: 'total_meastime', desc: true }])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  // tat_index가 null인 행은 정렬 방향과 무관하게 항상 맨 뒤로 보냅니다 —
  // '모른다'를 0으로 취급하면 표본 미달 장비가 최상위/최하위로 몰립니다.
  return [...filteredRows.value].sort((a, b) => {
    const av = a[id]
    const bv = b[id]
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    return (av - bv) * dir
  })
})

const toggle = (eqpId: string) => {
  if (props.selected.includes(eqpId)) {
    emit('update:selected', props.selected.filter(id => id !== eqpId))
    return
  }
  if (props.selected.length >= props.maxSelected) return
  emit('update:selected', [...props.selected, eqpId])
}

const signalsFor = (row: RecipeTatEquipmentRow) => equipmentSignals(row, props.percentiles)

const columns: TableColumn<RecipeTatEquipmentRow>[] = [
  { id: 'pick', header: '', size: 44 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 120 },
  { accessorKey: 'fab_name', header: 'fab', size: 72 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 100 },
  {
    accessorKey: 'exec_count',
    header: '실행수',
    size: 88,
    cell: ({ row }) => row.original.exec_count.toLocaleString()
  },
  {
    accessorKey: 'total_meastime',
    header: '총 TAT',
    size: 130,
    cell: ({ row }) => formatSecondsAsDuration(row.original.total_meastime)
  },
  { accessorKey: 'occupancy', header: '점유율', size: 88 },
  {
    accessorKey: 'avg_meastime',
    header: '평균',
    size: 110,
    cell: ({ row }) => formatSecondsAsDuration(Math.round(row.original.avg_meastime))
  },
  { accessorKey: 'recipe_count', header: '레시피수', size: 88 },
  { accessorKey: 'tat_index', header: 'TAT index', size: 100 },
  { id: 'signals', header: '신호', size: 140 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
