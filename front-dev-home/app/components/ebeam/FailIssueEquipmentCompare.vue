<template>
  <div class="space-y-3">
    <!-- 선택 요약: 플릿 표에서 이미 받은 행으로 계산하므로 추가 요청 없음 -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-[var(--sk-r-card)] px-3.5 py-2.5">
      <span
        v-for="row in rows"
        :key="row.eqp_id"
        class="inline-flex h-7 items-center gap-2 rounded-[var(--sk-r-chip)] px-2.5 text-[12px] ring-1 ring-(--sk-border-soft)"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: colorByEqpId.get(row.eqp_id) }"
        />
        <span class="font-mono font-semibold text-(--sk-ink)">{{ row.eqp_id }}</span>
        <span class="text-(--sk-ink-muted)">
          측정 {{ row.exec_count.toLocaleString() }} ·
          레시피 {{ row.recipe_count }} ·
          실패 {{ chipFailCount(row).toLocaleString() }}
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
              <span
                class="mx-1 h-4 w-px bg-(--sk-border-soft)"
                aria-hidden="true"
              />
              <SkNavPill
                v-for="type in CHART_TYPES"
                :key="type.value"
                size="sm"
                :label="type.label"
                :icon="type.icon"
                :active="chartType === type.value"
                @click="chartType = type.value"
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
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="sk-title">
              레시피별 fail 비교
            </h3>
            <span class="sk-meta">
              선택한 장비에서 실행한 레시피를 모두 모은 표입니다. 그 장비에서 실행 이력이 없는 레시피는 —로 표시합니다.
            </span>
          </div>
          <!-- 표는 페이지 단위로 보이지만 내보내기는 합집합 전체를 냅니다 —
               페이지를 넘겨가며 25행씩 붙이는 것이 이 버튼이 없앨 일입니다. -->
          <div class="flex items-center gap-2">
            <UTooltip text="클립보드 복사">
              <UButton
                size="xs"
                color="neutral"
                variant="outline"
                icon="i-lucide-clipboard"
                aria-label="레시피별 fail 비교를 클립보드에 복사"
                :disabled="sortedRecipes.length === 0"
                @click="copyMatrix"
              />
            </UTooltip>
          </div>
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
import { h } from 'vue'
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatRate,
  useFailIssueApi,
  type FailIssueEquipmentCompareResponse,
  type FailIssueEquipmentRecipeRow,
  type FailIssueEquipmentRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'
import { copyTableToClipboard } from '~/utils/tableExport'
import { filterRecipeStatusTrendPoints } from '~/utils/recipeStatusTrend'

const props = defineProps<{
  toolType: FailIssueToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: FailIssueEquipmentRow[]
  section: 'align' | 'meas'
  anchorDate?: string
  includeToday: boolean
}>()

// 통합 워크북은 플릿 행(부모가 가짐)과 이 응답을 한 파일에 담아야 합니다.
// 부모가 캐시 키를 다시 조립해 훔쳐보는 대신 올려보냅니다 — 키 문자열이 두
// 곳에 살면 한쪽이 바뀔 때 조용히 빈 시트가 나옵니다.
const emit = defineEmits<{
  loaded: [FailIssueEquipmentCompareResponse | null]
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

// 선은 추세를, 막대는 하루치 크기를 읽게 합니다. 실패 건수는 0인 날이 많아
// 선으로 그리면 바닥에 붙어 며칠이 0인지 세기 어렵습니다.
const CHART_TYPES = [
  { value: 'line', label: '선', icon: 'i-lucide-trending-up' },
  { value: 'bar', label: '막대', icon: 'i-lucide-bar-chart-3' }
] as const
type ChartType = typeof CHART_TYPES[number]['value']

const chartType = ref<ChartType>('line')

const chipFailCount = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_count : row.meas_fail_count

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

watch(data, value => emit('loaded', value ?? null), { immediate: true })

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

// 헤더의 「오늘 데이터」 토글이 실제로 무언가를 거르는 유일한 지점입니다.
// `emit('loaded')` 는 필터 이전의 `data` 를 올려보내므로 Excel 의 「일별추이」
// 시트는 전 기간을 유지합니다 — 한 파일 안에서 시트마다 기준일이 달라지는
// 쪽이 더 나쁩니다.
//
// x축 dates 와 series 를 반드시 **둘 다** 여기서 파생시켜야 합니다. 한쪽만
// 거르면 축과 데이터가 하루씩 어긋나고, 그 어긋남은 차트가 조용히 잘못된
// 날짜에 값을 찍는 형태로만 드러납니다.
const visibleTrends = computed(() => trends.value.map(series => ({
  ...series,
  points: filterRecipeStatusTrendPoints(series.points, props.anchorDate, props.includeToday)
})))

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
  const dates = visibleTrends.value[0]?.points.map(point => point.date) ?? []
  const isRate = trendMetric.value === 'rate'
  const isBar = chartType.value === 'bar'
  return {
    // 막대에서는 세로선 포인터가 어느 막대를 짚었는지 흐립니다 — 그 칸 전체를
    // 덮는 shadow 가 축 트리거의 범위와 맞습니다.
    tooltip: { trigger: 'axis', axisPointer: { type: isBar ? 'shadow' : 'line' } },
    legend: {
      top: 0,
      textStyle: { fontSize: 10 },
      data: visibleTrends.value.map(series => series.eqp_id)
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
    //
    // 막대는 쌓지 않고 나란히 둡니다(기본 grouped). 장비끼리 비교하려고 고른
    // 화면이고, 비율 지표는 애초에 더할 수 있는 값이 아닙니다.
    series: visibleTrends.value.map((series) => {
      const color = colorByEqpId.value.get(series.eqp_id)
      const data = seriesValues(series.points)
      if (isBar) {
        return {
          type: 'bar' as const,
          name: series.eqp_id,
          barMaxWidth: 18,
          itemStyle: { color },
          data
        }
      }
      return {
        type: 'line' as const,
        name: series.eqp_id,
        smooth: true,
        showSymbol: false,
        itemStyle: { color },
        lineStyle: { color },
        data
      }
    })
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
    header: 'fail 합계',
    size: 90,
    cell: ({ row }) => rowTotalFails(row.original).toLocaleString()
  },
  ...(data.value?.eqp_ids ?? []).map((eqpId, index) => ({
    id: `eqp-${eqpId}`,
    // 헤더는 두 줄입니다: eqp_id 와, 그 칸의 숫자가 무엇인지(fail / 실행수 (fail율)).
    // 근거는 RecipeTatEquipmentCompare.vue 의 같은 블록에 있습니다.
    header: () => h('div', { class: 'leading-tight' }, [
      h('div', eqpId),
      h('div', { class: 'font-normal' }, 'fail / 실행수 (fail율)')
    ]),
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

// 매트릭스 내보내기

// 화면은 한 칸에 "fail/exec (비율)"을 합쳐 보여주지만, 복사는 장비마다 세 열로
// 풉니다 — 합쳐진 문자열은 스프레드시트에서 다시 쪼개야 하는 값입니다.
// 축(align/meas)은 화면과 같은 것만 냅니다.
const matrixTable = () => {
  const eqpIds = data.value?.eqp_ids ?? []
  const prefix = props.section === 'align' ? 'align' : 'meas'
  return {
    headers: [
      'full_name',
      `total_${prefix}_fail_count`,
      ...eqpIds.flatMap(eqpId => [
        `${eqpId}_exec_count`,
        `${eqpId}_${prefix}_fail_count`,
        `${eqpId}_${prefix}_fail_rate_pct`
      ])
    ],
    data: sortedRecipes.value.map(row => [
      row.full_name,
      rowTotalFails(row),
      ...eqpIds.flatMap((_, index) => {
        const cell = row.cells[index]
        // 돌지 않은 장비는 화면에서 —입니다. 비율을 0으로 채우면 "돌았는데
        // 한 번도 실패하지 않았다"로 읽히므로 빈 칸으로 둡니다.
        if (!cell || cell.exec_count === 0) return [0, 0, '']
        const fails = cellFails(cell)
        return [cell.exec_count, fails, (fails / cell.exec_count * 100).toFixed(2)]
      })
    ])
  }
}

const toast = useToast()

const copyMatrix = async () => {
  const { headers, data: rows } = matrixTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

// 헤더에 배경을 주지 않는 이유는 FailIssueFleetTable.vue의 같은 블록에 있습니다.
const tableUi = analyticsTableUi
</script>
