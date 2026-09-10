<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          장비 목록
        </h3>
        <span class="sk-count-chip">
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
        <!-- 내보내기는 화면에 보이는 것(검색·정렬 적용 후)을 그대로 냅니다.
             랭킹 표(FailIssueRankingTable)와 같은 계약입니다: 표는 행만
             올려보내고, 헤더·파일명은 조회 범위를 아는 부모가 짭니다. -->
        <UTooltip text="클립보드 복사">
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            aria-label="장비 목록을 클립보드에 복사"
            :disabled="sortedRows.length === 0"
            @click="emit('copy', sortedRows)"
          />
        </UTooltip>
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-file-spreadsheet"
          label="Excel"
          :disabled="sortedRows.length === 0"
          @click="emit('download', sortedRows)"
        />
      </div>
    </div>

    <UTable
      v-model:sorting="sorting"
      :columns="columns"
      :data="sortedRows"
      :sorting-options="sortingOptions"
      sticky="header"
      :ui="tableUi"
    >
      <template
        v-for="id in sortableColumnIds"
        :key="id"
        #[`${id}-header`]="{ column }"
      >
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
      </template>

      <template #pick-cell="{ row }">
        <UCheckbox
          :model-value="selected.includes(row.original.eqp_id)"
          :disabled="!selected.includes(row.original.eqp_id) && selected.length >= maxSelected"
          @update:model-value="toggle(row.original.eqp_id)"
        />
      </template>

      <template #fail_count-cell="{ row }">
        {{ failCount(row.original).toLocaleString() }}
      </template>

      <template #fail_rate-cell="{ row }">
        {{ formatRate(failRate(row.original)) }}
      </template>
    </UTable>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import {
  formatRate,
  type FailIssueEquipmentRow
} from '~/composables/useFailIssueApi'

const props = defineProps<{
  rows: FailIssueEquipmentRow[]
  selected: string[]
  maxSelected: number
  // 어느 실패 축을 그릴지. 응답은 두 축을 다 담고 있고 열만 갈아 끼웁니다.
  section: 'align' | 'meas'
}>()

const emit = defineEmits<{
  'update:selected': [string[]]
  'download': [rows: FailIssueEquipmentRow[]]
  'copy': [rows: FailIssueEquipmentRow[]]
}>()

const search = ref('')

// section 별 필드 접근자. 문자열 인덱싱을 한 곳에 가둬서 열 정의·정렬·
// 툴팁이 서로 다른 축을 읽는 사고를 막습니다.
const failCount = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_count : row.meas_fail_count
const failRate = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_rate : row.meas_fail_rate

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(row =>
    row.eqp_id.toLowerCase().includes(q)
    || row.eqp_model_cd.toLowerCase().includes(q)
    || row.fab_name.toLowerCase().includes(q))
})

const sortableColumnIds = [
  'exec_count', 'fail_count', 'fail_rate', 'recipe_count'
] as const
type SortableColumnId = typeof sortableColumnIds[number]

const sorting = ref<SortingState>([{ id: 'fail_count', desc: true }])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

// 이 표는 자기 행을 스스로 정렬합니다(`filteredRows` 를 검색으로 줄인 뒤
// `sortedRows` 에서 정렬). `manualSorting` 이 왜 지워지면 안 되는지는
// utils/tableSorting.ts 에 한 번만 적혀 있습니다 — 지우면 UTable 이
// 정렬된 배열을 한 번 더 정렬해 검색 결과와 순서가 어긋납니다.
const sortingOptions = MANUAL_SORTING_OPTIONS

const sortValue = (row: FailIssueEquipmentRow, id: SortableColumnId): number => {
  if (id === 'exec_count') return row.exec_count
  if (id === 'recipe_count') return row.recipe_count
  if (id === 'fail_count') return failCount(row)
  return failRate(row)
}

const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  return [...filteredRows.value].sort((a, b) => (sortValue(a, id) - sortValue(b, id)) * dir)
})

const toggle = (eqpId: string) => {
  if (props.selected.includes(eqpId)) {
    emit('update:selected', props.selected.filter(id => id !== eqpId))
    return
  }
  if (props.selected.length >= props.maxSelected) return
  emit('update:selected', [...props.selected, eqpId])
}

const failLabel = computed(() => props.section === 'align' ? 'align fail' : 'meas fail')

const columns = computed<TableColumn<FailIssueEquipmentRow>[]>(() => [
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
  { id: 'fail_count', header: failLabel.value, size: 96 },
  { id: 'fail_rate', header: 'fail율', size: 88 },
  { accessorKey: 'recipe_count', header: '레시피수', size: 88 }
])

// 행 hover는 zinc 스케일을 직접 쓰는 두 곳 중 하나로 허용됩니다(DESIGN.md).
// 헤더에는 배경이 필요 없습니다: sticky 헤더가 이미 테마 surface 위에 앉아
// 있어서, 여기에 tint를 주면 더 차가운 두 번째 카드가 하나 더 생길 뿐입니다.
const tableUi = analyticsTableUi
</script>
