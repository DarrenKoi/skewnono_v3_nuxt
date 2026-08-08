<template>
  <div class="space-y-3">
    <!-- 선택 요약: 플릿 표에서 이미 받은 행으로 계산하므로 추가 요청 없음 -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-[var(--sk-r-card)] px-3.5 py-2.5">
      <span
        v-for="row in rows"
        :key="row.eqp_id"
        class="inline-flex h-7 items-center gap-2 rounded-md px-2.5 text-[11px] ring-1 ring-(--sk-border-soft)"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: colorByEqpId.get(row.eqp_id) }"
        />
        <span class="font-mono font-semibold text-(--sk-ink)">{{ row.eqp_id }}</span>
        <span class="text-(--sk-ink-muted)">
          {{ row.exec_count.toLocaleString() }} runs ·
          {{ chipFailCount(row).toLocaleString() }} fails ·
          {{ formatRate(chipFailRate(row)) }}
        </span>
      </span>
    </div>

    <!-- 선택이 바뀌면 이전 선택의 차트/열을 계속 보여주는 대신 로딩으로
         바꿉니다. mock 에서는 즉시라 눈에 띄지 않지만, office 는 composite
         집계라 초 단위입니다 — 그 사이 화면에 남는 숫자는 지금 체크된
         장비의 것이 아닙니다. 위의 선택 요약 칩은 플릿 표 행(props)에서
         나오므로 요청과 무관하게 즉시 맞고, 그래서 로딩 밖에 둡니다. -->
    <AppLoadingState
      v-if="status === 'pending'"
      title="장비 비교 데이터를 불러오는 중입니다."
    />

    <template v-else>
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-trending-up"
                class="h-4 w-4 text-(--sk-ink-muted)"
              />
              <h3 class="sk-title">
                장비별 일별 {{ aspectLabel }}
              </h3>
            </div>
            <!-- 손으로 만든 흰색/zinc 세그먼트 컨트롤은 DESIGN.md가 드리프트로
                 지목하는 패턴입니다 — 트레이 배경이 raw zinc를 테마 서피스
                 위로 끌어들이는 지점이었습니다. 토큰화된 SkNavPill로 대체합니다. -->
            <div class="inline-flex items-center gap-1">
              <SkNavPill
                v-for="metric in TREND_METRICS"
                :key="metric.value"
                size="sm"
                :label="metric.label"
                :active="trendMetric === metric.value"
                @click="trendMetric = metric.value"
              />
            </div>
          </div>
        </template>
        <div
          ref="trendEl"
          class="h-[360px] w-full"
        />
      </UCard>

      <div class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <h3 class="sk-title">
            레시피별 fail 비교
          </h3>
          <span class="sk-meta">
            선택 장비들이 돈 레시피의 합집합입니다. 돌지 않은 장비는 —로 표시됩니다.
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
            {{ pageStart }}–{{ pageEnd }} of {{ sortedRecipes.length.toLocaleString() }}
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
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatRate,
  useFailIssueApi,
  type FailIssueEquipmentRecipeRow,
  type FailIssueEquipmentRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'

const props = defineProps<{
  toolType: FailIssueToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: FailIssueEquipmentRow[]
  section: 'align' | 'meas'
}>()

const { fetchEquipmentCompare } = useFailIssueApi()
const { palette } = useEchartsTheme()

const aspectLabel = computed(() => props.section === 'align' ? 'Align fail' : 'Meas fail')

const TREND_METRICS = [
  { value: 'count', label: '개수' },
  { value: 'rate', label: '비율' }
] as const
type TrendMetric = typeof TREND_METRICS[number]['value']

const trendMetric = ref<TrendMetric>('count')

const chipFailCount = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_count : row.meas_fail_count
const chipFailRate = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_rate : row.meas_fail_rate

// 칩 점 색과 트렌드 라인 색이 같은 eqp_id에 대해 어긋나지 않도록 하나의
// 인덱스에서만 파생시킵니다. eqpIds(요청 순서)가 정준입니다 — API가 이
// 순서 그대로 trends.eqp_id를 echo하고, rows(플릿 표 순서로 필터된
// selectedRows)는 클릭 순서와 다를 수 있어 그 자체로는 색 소스가 될 수
// 없습니다.
const colorByEqpId = computed(() => new Map(
  props.eqpIds.map((id, index) => [id, palette.value[index % palette.value.length]])
))

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined,
  eqpIds: props.eqpIds
}))

// 선택 순서가 캐시 키를 흔들지 않도록 정렬해서 넣습니다 — 같은 3대를
// 다른 순서로 고르면 같은 데이터입니다. section 은 키에 넣지 않습니다:
// 응답이 두 축을 다 담고 있어 탭을 오가도 같은 데이터입니다.
const cacheKey = computed(
  () => `fail-issue-compare:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${props.dateRange.start || 'auto'}:${props.dateRange.end || 'auto'}`
    + `:${[...props.eqpIds].sort().join(',')}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchEquipmentCompare(queryParams.value),
  { watch: [cacheKey] }
)

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

const cellFails = (cell: { align_fail_count: number, meas_fail_count: number }) =>
  props.section === 'align' ? cell.align_fail_count : cell.meas_fail_count

const rowTotalFails = (row: FailIssueEquipmentRecipeRow) =>
  props.section === 'align' ? row.total_align_fail_count : row.total_meas_fail_count

// 백엔드는 활성 탭을 모르므로 두 지표의 합으로 정렬해 보냅니다. 여기서
// 활성 축 기준으로 다시 정렬합니다 — 백엔드 순서가 결정적이라 이 정렬도
// 안정적입니다.
const sortedRecipes = computed(
  () => [...recipes.value].sort((a, b) => rowTotalFails(b) - rowTotalFails(a))
)

// 트렌드 오버레이

const trendEl = ref<HTMLDivElement | null>(null)

const seriesValues = (points: { exec_count: number, align_fail_count: number, meas_fail_count: number }[]) =>
  points.map((point) => {
    const fails = props.section === 'align' ? point.align_fail_count : point.meas_fail_count
    if (trendMetric.value === 'count') return fails
    // 비율은 프론트에서 계산합니다 — 백엔드가 이미 분자와 분모를 다
    // 내려주므로 세 번째 필드를 추가할 이유가 없습니다.
    return point.exec_count > 0 ? Number((fails / point.exec_count * 100).toFixed(2)) : 0
  })

const trendOption = computed<EChartsOption>(() => {
  const dates = trends.value[0]?.points.map(point => point.date) ?? []
  const isRate = trendMetric.value === 'rate'
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
      axisLabel: {
        fontSize: 10,
        formatter: isRate ? '{value}%' : '{value}'
      }
    },
    // areaStyle을 쓰지 않습니다: 다중 시리즈에 채움을 주면 hover 시 blur가
    // 채움을 지워서 화면이 깨진 것처럼 보입니다.
    series: trends.value.map(series => ({
      type: 'line' as const,
      name: series.eqp_id,
      smooth: true,
      showSymbol: false,
      itemStyle: { color: colorByEqpId.value.get(series.eqp_id) },
      lineStyle: { color: colorByEqpId.value.get(series.eqp_id) },
      data: seriesValues(series.points)
    }))
  }
})

useEchart(trendEl, trendOption, { exportName: 'equipment-fail-trend' })

// 레시피 매트릭스

const PAGE_SIZE = 25
const currentPage = ref(1)
watch([cacheKey, () => props.section], () => {
  currentPage.value = 1
})

const {
  pageCount, pageStart, pageEnd, pagedRows: pagedRecipes
} = usePagedRows(sortedRecipes, PAGE_SIZE, currentPage)

// 열은 응답의 eqp_ids 순서를 그대로 따릅니다. cells가 같은 순서로 0채움되어
// 오므로 인덱스로 바로 꽂습니다 — 백엔드가 길이를 보장합니다.
const columns = computed<TableColumn<FailIssueEquipmentRecipeRow>[]>(() => [
  { accessorKey: 'full_name', header: 'full name', size: 240 },
  {
    id: 'total_fails',
    header: '합계',
    size: 90,
    cell: ({ row }) => rowTotalFails(row.original).toLocaleString()
  },
  ...(data.value?.eqp_ids ?? []).map((eqpId, index) => ({
    id: `eqp-${eqpId}`,
    header: eqpId,
    size: 160,
    cell: ({ row }: { row: { original: FailIssueEquipmentRecipeRow } }) => {
      const cell = row.original.cells[index]
      if (!cell || cell.exec_count === 0) return '—'
      const fails = cellFails(cell)
      return `${fails.toLocaleString()}/${cell.exec_count.toLocaleString()}`
        + ` (${formatRate(fails / cell.exec_count)})`
    }
  }))
])

// 헤더에 배경을 주지 않는 이유는 FailIssueFleetTable.vue의 같은 블록에 있습니다.
const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 sk-label'
}
</script>
