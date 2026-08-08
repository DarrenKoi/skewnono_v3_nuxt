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
          {{ row.exec_count.toLocaleString() }} runs ·
          {{ formatSecondsCompact(row.total_meastime) }} ·
          {{ row.recipe_count }} recipes
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
                장비별 일별 TAT
              </h3>
            </div>
            <!-- 손으로 만든 세그먼트 컨트롤 대신 토큰화된 SkNavPill을 씁니다
                 (근거는 FailIssueEquipmentCompare.vue의 같은 블록). -->
            <div class="inline-flex items-center gap-1">
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
              레시피 구성 비교
            </h3>
            <span class="sk-meta">
              선택 장비들이 돈 레시피의 합집합입니다. 돌지 않은 장비는 0으로 표시됩니다.
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
                aria-label="레시피 구성 비교를 클립보드에 복사"
                :disabled="recipes.length === 0"
                @click="copyMatrix"
              />
            </UTooltip>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              icon="i-lucide-download"
              label="CSV"
              :disabled="recipes.length === 0"
              @click="downloadMatrixCsv"
            />
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
    </template>
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
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { todayStamp } from '~/utils/dateTime'

const props = defineProps<{
  toolType: RecipeTatToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: RecipeTatEquipmentRow[]
}>()

const { fetchRecipeTatEquipmentCompare } = useRecipeTatApi()
const { palette } = useEchartsTheme()

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
// 다른 순서로 고르면 같은 데이터입니다.
const cacheKey = computed(
  () => `recipe-tat-compare:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${props.dateRange.start || 'auto'}:${props.dateRange.end || 'auto'}`
    + `:${[...props.eqpIds].sort().join(',')}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeTatEquipmentCompare(queryParams.value),
  { watch: [cacheKey] }
)

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

// 트렌드 오버레이

const trendEl = ref<HTMLDivElement | null>(null)

// 선은 추세를, 막대는 하루치 크기를 읽게 합니다. 며칠만 조회했을 때 선은
// 점 두어 개를 잇는 데 그쳐 오히려 읽기 어렵습니다.
const CHART_TYPES = [
  { value: 'line', label: '선', icon: 'i-lucide-trending-up' },
  { value: 'bar', label: '막대', icon: 'i-lucide-bar-chart-3' }
] as const
type ChartType = typeof CHART_TYPES[number]['value']

const chartType = ref<ChartType>('line')

const trendOption = computed<EChartsOption>(() => {
  const dates = trends.value[0]?.points.map(point => point.date) ?? []
  const isBar = chartType.value === 'bar'
  return {
    // 막대에서는 세로선 포인터가 어느 막대를 짚었는지 흐립니다 — 그 칸 전체를
    // 덮는 shadow 가 축 트리거의 범위와 맞습니다.
    tooltip: { trigger: 'axis', axisPointer: { type: isBar ? 'shadow' : 'line' } },
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
    //
    // 막대는 쌓지 않고 나란히 둡니다(기본 grouped). 장비끼리 비교하려고
    // 고른 화면이라 합계를 보여주는 stack은 여기서 답이 아닙니다.
    series: trends.value.map((series) => {
      const color = colorByEqpId.value.get(series.eqp_id)
      const data = series.points.map(point => point.total_meastime)
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

useEchart(trendEl, trendOption, { exportName: 'equipment-tat-trend' })

// 레시피 매트릭스

const PAGE_SIZE = 25
const currentPage = ref(1)
watch(cacheKey, () => {
  currentPage.value = 1
})

const {
  pageCount, pageStart, pageEnd, pagedRows: pagedRecipes
} = usePagedRows(recipes, PAGE_SIZE, currentPage)

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

// 매트릭스 내보내기

// 화면은 한 칸에 "건수 · 시간"을 합쳐 보여주지만, CSV는 장비마다 두 열로
// 풉니다 — 합쳐진 문자열은 스프레드시트에서 다시 쪼개야 하는 값입니다.
const matrixTable = () => {
  const eqpIds = data.value?.eqp_ids ?? []
  return {
    headers: [
      'full_name',
      'total_meastime_sec',
      ...eqpIds.flatMap(eqpId => [`${eqpId}_meas_counts`, `${eqpId}_total_meastime_sec`])
    ],
    data: recipes.value.map(row => [
      row.full_name,
      row.total_meastime,
      ...eqpIds.flatMap((_, index) => {
        const cell = row.cells[index]
        return [cell?.meas_counts ?? 0, cell?.total_meastime ?? 0]
      })
    ])
  }
}

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-equipment-compare-${todayStamp()}.csv`
})

const toast = useToast()

const downloadMatrixCsv = () => {
  const { headers, data: rows } = matrixTable()
  downloadCsv(exportFileName.value, headers, rows)
}

const copyMatrix = async () => {
  const { headers, data: rows } = matrixTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

// 헤더에 배경을 주지 않는 이유는 RecipeTatFleetTable.vue의 같은 블록에 있습니다:
// sticky 헤더가 이미 테마 surface 위에 앉아 있습니다. 타입은 .sk-label에 맡깁니다.
const tableUi = analyticsTableUi
</script>
