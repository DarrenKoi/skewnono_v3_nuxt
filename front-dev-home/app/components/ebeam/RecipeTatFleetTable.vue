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
          icon="i-lucide-download"
          label="CSV"
          :disabled="sortedRows.length === 0"
          @click="emit('download', sortedRows)"
        />
      </div>
    </div>

    <p
      v-if="!peerGroupComparable"
      class="mb-3 flex items-start gap-1.5 sk-meta"
    >
      <UIcon
        name="i-lucide-info"
        class="mt-px h-3.5 w-3.5 shrink-0"
      />
      <span>
        조회 결과가 두 개 이상의 fab에 걸쳐 있습니다. 레시피 길이가 fab마다 달라
        신호 배지는 표시하지 않고, TAT index 열도 fab을 섞은 기준선으로 계산됩니다 —
        이 열로 정렬하면 장비가 아니라 fab이 줄세워집니다. 장비끼리 비교하려면
        fab을 하나만 선택하십시오.
      </span>
    </p>

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
        <span
          v-if="!peerGroupComparable"
          class="text-(--sk-ink-muted)"
        >—</span>
        <div
          v-else
          class="flex flex-wrap gap-1"
        >
          <span
            v-for="signal in signalsFor(row.original)"
            :key="signal"
            class="sk-signal-badge ring-1"
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
  // 또래 집단이 한 fab으로 이루어져 있는가. false면 배지를 하나도 달지
  // 않습니다 — 섞인 fab에서 배지는 장비가 아니라 fab을 가리킵니다
  // (근거는 utils/equipmentSignals.ts의 isPeerGroupComparable 위 주석).
  // 판정을 equipmentSignals() 안에 넣지 않은 이유도 같은 곳에 적혀 있습니다.
  peerGroupComparable: boolean
  selected: string[]
  maxSelected: number
}>()

const emit = defineEmits<{
  'update:selected': [string[]]
  'download': [rows: RecipeTatEquipmentRow[]]
  'copy': [rows: RecipeTatEquipmentRow[]]
}>()

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

// TAT index는 간접표준화 지표라 열 이름만으로는 읽히지 않습니다. 설명이 없으면
// 1.08을 "평균보다 8% 느림"이 아니라 점수로 읽습니다.
const TAT_INDEX_HEADER_TOOLTIP
  = '실제 총 TAT ÷ 이 장비의 레시피 구성이면 걸렸어야 할 TAT. '
    + '1.00보다 크면 같은 일을 평균보다 느리게 했다는 뜻입니다.'

// 여러 fab을 함께 조회하면 기준선이 fab을 섞어 계산됩니다. 배지와 달리 값을
// 지우지는 않습니다 — 같은 fab 안에서는 여전히 유효하기 때문입니다. 대신 경고를
// 정렬하려고 누르는 바로 그 헤더에 답니다. 표 위 문단만으로는 정렬하는 순간
// 손이 닿는 곳에 경고가 없습니다.
const TAT_INDEX_MIXED_FAB_TOOLTIP
  = '여러 fab을 함께 조회 중입니다. 기준선이 fab을 섞어 계산되어, 이 열로 '
    + '정렬하면 장비가 아니라 fab이 줄세워집니다.'

const headerTooltip = (id: SortableColumnId) => {
  if (id === 'occupancy') return OCCUPANCY_HEADER_TOOLTIP
  if (id !== 'tat_index') return undefined
  return props.peerGroupComparable ? TAT_INDEX_HEADER_TOOLTIP : TAT_INDEX_MIXED_FAB_TOOLTIP
}

const sorting = ref<SortingState>([{ id: 'total_meastime', desc: true }])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

// 이 표는 자기 행을 스스로 정렬합니다. `manualSorting` 이 왜 지워지면 안
// 되는지는 utils/tableSorting.ts 에 한 번만 적혀 있습니다 — 이 화면에서
// 구체적으로 깨지는 방식은 TAT index 오름차순에서 표본 미달 장비가 맨 위로
// 올라와 "판단 못 함"이 "가장 빠른 장비"로 읽히는 것입니다.
const sortingOptions = MANUAL_SORTING_OPTIONS

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

const signalsFor = (row: RecipeTatEquipmentRow) =>
  props.peerGroupComparable ? equipmentSignals(row, props.percentiles) : []

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

// 행 hover는 zinc 스케일을 직접 쓰는 두 곳 중 하나로 허용됩니다(DESIGN.md).
// 헤더에는 배경이 필요 없습니다: sticky 헤더가 이미 테마 surface 위에 앉아
// 있어서, 여기에 tint를 주면 더 차가운 두 번째 카드가 하나 더 생길 뿐입니다.
// 타입은 .sk-label(11px/600/ink-muted)에 맡깁니다 — 장비 리스트가 참조 사례.
const tableUi = analyticsTableUi
</script>
