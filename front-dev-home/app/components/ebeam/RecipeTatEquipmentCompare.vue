<template>
  <div class="space-y-3">
    <!-- 선택 요약: 플릿 표에서 이미 받은 행으로 계산하므로 추가 요청 없음 -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-2xl px-3.5 py-2.5">
      <span
        v-for="(row, index) in rows"
        :key="row.eqp_id"
        class="inline-flex h-7 items-center gap-2 rounded-md px-2.5 text-[11px] ring-1 ring-(--sk-border-soft)"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: palette[index % palette.length] }"
        />
        <span class="font-mono font-semibold text-(--sk-ink)">{{ row.eqp_id }}</span>
        <span class="text-(--sk-ink-muted)">
          {{ row.exec_count.toLocaleString() }} runs ·
          {{ formatSecondsCompact(row.total_meastime) }} ·
          {{ row.recipe_count }} recipes
        </span>
      </span>
    </div>

    <UCard class="dashboard-surface rounded-2xl">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-trending-up"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h3 class="sk-title">
            장비별 일별 TAT
          </h3>
        </div>
      </template>
      <div
        ref="trendEl"
        class="h-[360px] w-full"
      />
    </UCard>

    <div class="dashboard-surface rounded-2xl px-3.5 py-3">
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          레시피 구성 비교
        </h3>
        <span class="sk-meta">
          선택 장비들이 돈 레시피의 합집합입니다. 돌지 않은 장비는 0으로 표시됩니다.
        </span>
      </div>

      <UTable
        :columns="columns"
        :data="pagedRecipes"
        sticky="header"
        :ui="tableUi"
      />

      <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
        <span class="tabular-nums">
          {{ pageStart }}–{{ pageEnd }} of {{ recipes.length.toLocaleString() }}
        </span>
        <div class="flex gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            trailing-icon="i-lucide-chevron-right"
            :disabled="currentPage >= pageCount"
            @click="currentPage += 1"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatSecondsAsDuration,
  formatSecondsCompact,
  useRecipeTatApi,
  type RecipeTatEquipmentRecipeRow,
  type RecipeTatEquipmentRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'

const props = defineProps<{
  toolType: RecipeTatToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: RecipeTatEquipmentRow[]
}>()

const { fetchRecipeTatEquipmentCompare } = useRecipeTatApi()
const { palette } = useEchartsTheme()

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined,
  eqpIds: props.eqpIds
}))

// 선택 순서가 캐시 키를 흔들지 않도록 정렬해서 넣습니다 — 같은 3대를
// 다른 순서로 고르면 같은 데이터입니다.
const cacheKey = computed(
  () => `recipe-tat-compare:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${props.dateRange.start || 'auto'}:${props.dateRange.end || 'auto'}`
    + `:${[...props.eqpIds].sort().join(',')}`
)

const { data } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeTatEquipmentCompare(queryParams.value),
  { watch: [cacheKey] }
)

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

// 트렌드 오버레이

const trendEl = ref<HTMLDivElement | null>(null)

const trendOption = computed<EChartsOption>(() => {
  const dates = trends.value[0]?.points.map(point => point.date) ?? []
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      textStyle: { fontSize: 10 },
      data: trends.value.map(series => series.eqp_id)
    },
    grid: { left: 8, right: 24, top: 32, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 10,
        interval: Math.max(0, Math.floor(dates.length / 8) - 1)
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, formatter: (v: number) => formatSecondsCompact(v) }
    },
    // areaStyle을 쓰지 않습니다: 다중 시리즈에 채움을 주면 hover 시 blur가
    // 채움을 지워서 화면이 깨진 것처럼 보입니다.
    series: trends.value.map((series, index) => ({
      type: 'line' as const,
      name: series.eqp_id,
      smooth: true,
      showSymbol: false,
      itemStyle: { color: palette.value[index % palette.value.length] },
      lineStyle: { color: palette.value[index % palette.value.length] },
      data: series.points.map(point => point.total_meastime)
    }))
  }
})

useEchart(trendEl, trendOption, { exportName: 'equipment-tat-trend' })

// 레시피 매트릭스

const PAGE_SIZE = 25
const currentPage = ref(1)
watch(cacheKey, () => {
  currentPage.value = 1
})

const pageCount = computed(() => Math.max(1, Math.ceil(recipes.value.length / PAGE_SIZE)))
const pageStart = computed(
  () => recipes.value.length === 0 ? 0 : ((currentPage.value - 1) * PAGE_SIZE) + 1
)
const pageEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, recipes.value.length))
const pagedRecipes = computed(
  () => recipes.value.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE)
)

// 열은 응답의 eqp_ids 순서를 그대로 따릅니다. cells가 같은 순서로 0채움되어
// 오므로 인덱스로 바로 꽂습니다 — 백엔드가 길이를 보장합니다.
const columns = computed<TableColumn<RecipeTatEquipmentRecipeRow>[]>(() => [
  { accessorKey: 'full_name', header: 'full name', size: 240 },
  {
    accessorKey: 'total_meastime',
    header: '합계',
    size: 110,
    cell: ({ row }) => formatSecondsAsDuration(row.original.total_meastime)
  },
  ...(data.value?.eqp_ids ?? []).map((eqpId, index) => ({
    id: `eqp-${eqpId}`,
    header: eqpId,
    size: 150,
    cell: ({ row }: { row: { original: RecipeTatEquipmentRecipeRow } }) => {
      const cell = row.original.cells[index]
      if (!cell || cell.meas_counts === 0) return '—'
      return `${cell.meas_counts.toLocaleString()} · ${formatSecondsCompact(cell.total_meastime)}`
    }
  }))
])

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
