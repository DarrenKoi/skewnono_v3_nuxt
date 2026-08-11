<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe TAT"
      :subtitle="metaSubtitle"
      :as-of="summary?.anchor_date"
      cadence="1시간 주기"
    >
      <template #toggle>
        <div class="flex flex-wrap items-center gap-2.5">
          <!-- 뷰 전환은 NAVIGATE 동작이라 SkNavPill(ink fill)입니다. 직접 만든
               white/zinc 세그먼트 컨트롤은 DESIGN.md가 이름을 대어 금지한
               패턴이었습니다 — 트레이 배경이 zinc를 종이 위로 끌고 들어옵니다. -->
          <div class="inline-flex items-center gap-1">
            <SkNavPill
              v-for="mode in VIEW_MODES"
              :key="mode.value"
              :label="mode.label"
              :icon="mode.icon"
              :active="viewMode === mode.value"
              @click="viewMode = mode.value"
            />
          </div>
          <EbeamDateRangePopover
            v-model="dateRange"
            :anchor-date="summary?.anchor_date"
            trigger-class="h-9 px-3.5 text-sm"
          />
          <span
            v-if="viewMode === 'by-device' && selectedLot"
            class="inline-flex h-7 items-center gap-1 rounded-md bg-(--sk-accent-tint) px-2.5 font-mono text-[12px] font-semibold text-(--sk-accent)"
          >
            <UIcon
              name="i-lucide-target"
              class="h-3.5 w-3.5"
            />
            {{ selectedLot }}
          </span>
        </div>
      </template>

      <!-- 「데이터 기준」 배지 바로 오른쪽. 세 뷰 모드가 공유하는 표시 설정이라
           특정 차트 카드가 아니라 헤더가 제자리입니다. 뷰 모드·로딩·빈 상태와
           무관하게 항상 렌더합니다 — 상태에 따라 사라지면 이 줄의 폭이
           흔들립니다. -->
      <template #actions>
        <USwitch
          v-model="includeToday"
          size="sm"
          label="오늘 데이터"
          class="shrink-0"
        />
      </template>
    </EbeamMetaBar>

    <!-- Device picker (디바이스별 mode only) -->
    <EbeamAnalyticsDevicePicker
      v-if="viewMode === 'by-device'"
      v-model:selected-lot="selectedLot"
      :devices="deviceList"
      :get-title="recipeDeviceTitle"
      :reset-key="devicesCacheKey"
    />

    <!-- 장비별: 별도 컴포넌트 트리. 기존 본문은 건드리지 않습니다. -->
    <EbeamRecipeTatEquipmentView
      v-if="viewMode === 'by-equipment'"
      :fabs="fabs"
      :tool-type="toolType"
      :date-range="dateRange"
      :anchor-date="summary?.anchor_date"
      :include-today="includeToday"
    />

    <!-- 디바이스별 mode without a selection: prompt instead of dashboard -->
    <div
      v-else-if="viewMode === 'by-device' && !selectedLot"
      class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-mouse-pointer-click"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 sk-body">
        디바이스를 선택해주세요
      </p>
      <p class="mt-1 sk-meta">
        위에서 디바이스 칩을 클릭하면 해당 디바이스의 Recipe TAT 정보가 표시됩니다.
      </p>
    </div>

    <template v-else>
      <!-- Empty / loading state -->
      <AppLoadingState
        v-if="status === 'pending' && !rankingRows.length"
        title="Recipe TAT 데이터를 불러오는 중입니다."
      />
      <AppEmptyState
        v-else-if="!rankingRows.length"
        title="No measurements in this range"
        description="Try widening the date range or selecting a different fab."
      />

      <template v-else>
        <!-- Charts -->
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <UCard class="dashboard-surface">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <UIcon
                    name="i-lucide-bar-chart-horizontal"
                    class="h-4 w-4 text-(--sk-ink-muted)"
                  />
                  <h3 class="sk-title">
                    {{ barChartTitle }}
                  </h3>
                  <span
                    v-if="tableSearch.trim()"
                    class="sk-meta"
                  >표 검색 적용됨</span>
                </div>
                <USelect
                  v-model="topNLimitText"
                  size="xs"
                  :items="topNOptions"
                  class="w-[6rem]"
                />
              </div>
            </template>
            <div
              ref="barEl"
              class="h-[400px] w-full"
            />
          </UCard>

          <UCard class="dashboard-surface">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="sk-title">
                  Daily TAT trend
                </h3>
              </div>
            </template>
            <div
              ref="trendEl"
              class="h-[400px] w-full"
            />
          </UCard>
        </div>

        <!-- Table. The bar chart above reads this table's sort and its
             sorted rows, so that view comes back out via update:state rather
             than being recomputed here. -->
        <!-- @vue-generic {RecipeTatRow} -->
        <EbeamFailIssueRankingTable
          title="Ranked recipes"
          search-placeholder="Search recipe / class…"
          csv-label="CSV 다운로드"
          :summary-items="tatSummaryItems"
          :rows="rankingRows"
          :columns="columns"
          :sortable-ids="sortableColumnIds"
          :default-sort-id="DEFAULT_SORT_ID"
          :reset-key="cacheKey"
          :search-predicate="rankingSearchPredicate"
          @update:state="onTableState"
          @download="downloadRankingCsv"
          @copy="copyRankingTable"
        >
          <template #title-extra>
            <span
              v-if="rankingLimit && rankingRows.length >= rankingLimit"
              class="font-mono text-[10px] text-(--sk-warn)"
            >capped at {{ rankingLimit.toLocaleString() }}</span>
          </template>
          <template #actions-cell="{ row }">
            <EbeamRecipeRowActions
              :tool-type="toolType"
              :fab-segment="fabSegment"
              :fab-names="row.original.fab_names ?? []"
              :recipe-name="row.original.recipe_name"
            />
          </template>
        </EbeamFailIssueRankingTable>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import {
  formatSecondsAsDuration,
  formatSecondsCompact,
  useRecipeTatApi,
  type RecipeTatDeviceRow,
  type RecipeTatRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import {
  buildTatSummaryItems,
  resolveRecipeStatusSummaryValue
} from '~/utils/recipeStatusSummary'
import { filterRecipeStatusTrendPoints } from '~/utils/recipeStatusTrend'
import { buildFabSegment } from '~/utils/fab'
import { todayStamp } from '~/utils/dateTime'
import type { RankingTableState } from '~/utils/rankingTable'

const props = defineProps<{
  fabs: string[]
  toolLabel: string
  toolType: RecipeTatToolType
}>()

const includeToday = defineModel<boolean>('includeToday', { required: true })

const identity = computed(() => `${props.toolLabel} · ${props.fabs.join(' + ')}`)

const fabSegment = computed(() => buildFabSegment(props.fabs))

// Empty means "let the server resolve its default window"; computing
// "today" locally drifts past the mock's ANCHOR_TIME for long-running
// Flask processes.
const userDateRange = ref({ start: '', end: '' })

const topNOptions = [
  { label: 'Top 10', value: '10' },
  { label: 'Top 20', value: '20' },
  { label: 'Top 30', value: '30' },
  { label: 'Top 50', value: '50' }
]
const topNLimitText = ref('20')
const topNLimit = computed(() => Number.parseInt(topNLimitText.value, 10))

// Selection state is intentionally local — not shared with `useDeviceCart`.
// Recipe-tat asks "which recipes consume my time on this one device?",
// independent of the device-statistics compare cart.
const VIEW_MODES = [
  { value: 'summary', label: '전체 요약', icon: 'i-lucide-layers' },
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' },
  { value: 'by-equipment', label: '장비별', icon: 'i-lucide-microscope' }
] as const
type ViewMode = typeof VIEW_MODES[number]['value']

const viewMode = ref<ViewMode>('summary')
const metaSubtitle = computed(() => {
  if (viewMode.value === 'by-device') return 'Recipe별 측정 시간 (TAT) 디바이스별로 분석합니다.'
  if (viewMode.value === 'by-equipment') return '장비(eqp_id)별 측정 부하와 소요 시간을 비교합니다.'
  return 'Recipe별 측정 시간 (TAT)을 Fab 기준으로 분석합니다.'
})
const selectedLot = ref<string | null>(null)

const {
  fetchRecipeTatRanking,
  fetchRecipeTatSummary,
  fetchRecipeTatDailyTrend,
  fetchRecipeTatDevices
} = useRecipeTatApi()

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: userDateRange.value.start || undefined,
  endDate: userDateRange.value.end || undefined,
  // No limit: the backend treats an omitted/0 limit as "every recipe in the
  // date range" — a fixed cap silently truncated fleet-wide rankings.
  lotCd: viewMode.value === 'by-device' ? (selectedLot.value ?? undefined) : undefined
}))

// `auto` placeholder keeps the cache key stable while the server resolves
// the default window on first fetch.
const cacheKey = computed(
  () => `recipe-tat:${queryParams.value.toolType}:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
    + `:${queryParams.value.lotCd ?? '*'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  async () => {
    const [ranking, summary, daily] = await Promise.all([
      fetchRecipeTatRanking(queryParams.value),
      fetchRecipeTatSummary(queryParams.value),
      fetchRecipeTatDailyTrend(queryParams.value)
    ])
    return { ranking, summary, daily }
  },
  { watch: [cacheKey] }
)

// Devices fetch deliberately excludes lot_cd from its cache key — this
// endpoint is the source of truth for which lot_cds exist in scope, so it
// must not be filtered by the current selection.
const devicesCacheKey = computed(
  () => `recipe-tat-devices:${queryParams.value.toolType}:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)
const { data: devicesData } = await useAsyncData(
  () => devicesCacheKey.value,
  () => fetchRecipeTatDevices(queryParams.value),
  { watch: [devicesCacheKey] }
)

const deviceList = computed(() => devicesData.value?.devices ?? [])
const recipeDeviceTitle = (device: RecipeTatDeviceRow) =>
  `${device.exec_count.toLocaleString()} runs · ${formatSecondsCompact(device.total_meastime)}`

const rankingRows = computed<RecipeTatRow[]>(() => data.value?.ranking.rows ?? [])
const rankingLimit = computed(() => data.value?.ranking.limit ?? 0)
const summary = computed(() => data.value?.summary)
const trendPoints = computed(() => data.value?.daily.points ?? [])
const visibleTrendPoints = computed(() => filterRecipeStatusTrendPoints(
  trendPoints.value,
  summary.value?.anchor_date,
  includeToday.value
))

// Falling back to the server-resolved window only inside the getter (vs.
// mirroring it into a ref) keeps echoed dates out of `userDateRange` and
// therefore out of `cacheKey`, avoiding a redundant refetch on first load.
const dateRange = computed({
  get: () => {
    if (userDateRange.value.start && userDateRange.value.end) {
      return userDateRange.value
    }
    return {
      start: data.value?.summary.start_date ?? '',
      end: data.value?.summary.end_date ?? ''
    }
  },
  set: (next) => {
    userDateRange.value = next
  }
})

const tatSummaryItems = computed(() => buildTatSummaryItems({
  totalTat: resolveRecipeStatusSummaryValue(
    status.value === 'pending',
    summary.value ? formatSecondsAsDuration(summary.value.total_tat_seconds) : undefined
  ),
  distinctRecipes: resolveRecipeStatusSummaryValue(
    status.value === 'pending',
    summary.value?.total_recipes.toLocaleString()
  ),
  totalExecutions: resolveRecipeStatusSummaryValue(
    status.value === 'pending',
    summary.value?.total_executions.toLocaleString()
  ),
  avgMeastime: resolveRecipeStatusSummaryValue(
    status.value === 'pending',
    summary.value
      ? formatSecondsAsDuration(Math.round(summary.value.avg_meastime))
      : undefined
  )
}))

// Daily trend line

// Shared theme palette so the two TAT charts read as distinct hues while
// staying theme-aware: bar = palette[0], trend = palette[1].
const { palette } = useEchartsTheme()

const trendEl = ref<HTMLDivElement | null>(null)

const trendOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: unknown) => {
      const arr = Array.isArray(params) ? params : [params]
      const first = arr[0] as { name?: string, dataIndex?: number }
      const idx = typeof first.dataIndex === 'number' ? first.dataIndex : 0
      const point = visibleTrendPoints.value[idx]
      if (!point) return ''
      return [
        `<b>${point.date}</b>`,
        `Total TAT: ${formatSecondsAsDuration(point.total_meastime)}`,
        `Executions: ${point.exec_count.toLocaleString()}`
      ].join('<br/>')
    }
  },
  grid: { left: 8, right: 24, top: 12, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: visibleTrendPoints.value.map(p => p.date),
    axisLabel: {
      fontSize: 10,
      interval: Math.max(0, Math.floor(visibleTrendPoints.value.length / 8) - 1)
    }
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      fontSize: 10,
      formatter: (v: number) => formatSecondsCompact(v)
    }
  },
  series: [{
    type: 'line',
    smooth: true,
    showSymbol: false,
    itemStyle: { color: palette.value[1] },
    lineStyle: { color: palette.value[1] },
    areaStyle: { color: palette.value[1], opacity: 0.18 },
    data: visibleTrendPoints.value.map(p => p.total_meastime)
  }]
}))

useEchart(trendEl, trendOption, { exportName: 'daily-tat-trend' })

// Table
//
// Search, sort, pagination and CSV live in EbeamFailIssueRankingTable. What
// stays here is only what the bar chart below also needs: the active sort and
// the rows in the order the table shows them, both mirrored back out of the
// component. Recomputing either locally would let the chart and the table
// disagree, which is exactly what the shared-sort design prevents.

const sortableColumnIds = ['meas_counts', 'avg_meastime', 'total_meastime'] as const
type SortableColumnId = typeof sortableColumnIds[number]

// Stated once. The table owns the sort, but the bar chart labels itself from it
// before the first `update:state` lands, so a second literal here would let the
// chart caption disagree with the table for one tick after the default changed.
const DEFAULT_SORT_ID: SortableColumnId = 'total_meastime'

const sorting = ref<SortingState>([
  { id: DEFAULT_SORT_ID, desc: true }
])
const sortedRankingRows = ref<RecipeTatRow[]>([])
const tableSearch = ref('')

const onTableState = (state: RankingTableState<RecipeTatRow>) => {
  tableSearch.value = state.search
  sorting.value = state.sorting
  sortedRankingRows.value = state.sortedRows
}

const rankingSearchPredicate = (row: RecipeTatRow, term: string) =>
  row.recipe_name.toLowerCase().includes(term)
  || row.class_name.toLowerCase().includes(term)
  || row.full_name.toLowerCase().includes(term)

// Bar chart — the table's leading rows, drawn (horizontal)
//
// Reads `sortedRankingRows` rather than the raw server ranking so the chart
// and the table can never disagree: the same search filter and the same sort
// column drive both, and the bars are literally the table's first N rows.
// The plotted measure follows the sorted column too — charting total TAT
// while the table is sorted by meas count would render non-monotonic bars
// that look broken.

const BAR_METRICS: Record<SortableColumnId, { label: string, format: (v: number) => string }> = {
  total_meastime: { label: 'total TAT', format: v => formatSecondsCompact(v) },
  avg_meastime: { label: 'avg meastime', format: v => formatSecondsCompact(v) },
  meas_counts: { label: 'meas count', format: v => v.toLocaleString() }
}

const barMetric = computed(() => {
  const id = (sorting.value[0]?.id ?? DEFAULT_SORT_ID) as SortableColumnId
  return { id, ...BAR_METRICS[id] }
})

const barRows = computed(() => sortedRankingRows.value.slice(0, topNLimit.value))

const barChartTitle = computed(() => {
  const descending = sorting.value[0]?.desc ?? true
  const edge = descending ? 'Top' : 'Bottom'
  return `${edge} ${topNLimit.value} recipes by ${barMetric.value.label}`
})

const barEl = ref<HTMLDivElement | null>(null)

const barOption = computed<EChartsOption>(() => {
  const metric = barMetric.value
  // ECharts renders the first category at the bottom of a horizontal bar,
  // so reverse to make the table's first row sit at the top of the chart.
  const reversed = [...barRows.value].reverse()

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as { name?: string, value?: number, dataIndex?: number }
        const idx = typeof first.dataIndex === 'number' ? first.dataIndex : 0
        const row = reversed[idx]
        if (!row) return ''
        return [
          `<b>${row.full_name}</b>`,
          `Total: ${formatSecondsAsDuration(row.total_meastime)}`,
          `Executions: ${row.meas_counts.toLocaleString()}`,
          `Avg: ${formatSecondsAsDuration(Math.round(row.avg_meastime))}`
        ].join('<br/>')
      }
    },
    grid: { left: 8, right: 24, top: 12, bottom: 28, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        formatter: (v: number) => metric.format(v)
      }
    },
    yAxis: {
      type: 'category',
      data: reversed.map(r => r.full_name),
      axisLabel: { fontSize: 10 }
    },
    series: [{
      type: 'bar',
      data: reversed.map(r => r[metric.id]),
      barMaxWidth: 18,
      itemStyle: { color: palette.value[0], borderRadius: [0, 4, 4, 0] }
    }]
  }
})

useEchart(barEl, barOption, { exportName: 'top-recipe-by-tat' })

const totalForShare = computed(
  () => rankingRows.value.reduce((sum, row) => sum + row.total_meastime, 0)
)

const columns: TableColumn<RecipeTatRow>[] = [
  { accessorKey: 'rank', header: '#', size: 56 },
  { accessorKey: 'full_name', header: 'full name', size: 240 },
  { id: 'actions', header: '', size: 96 },
  { accessorKey: 'class_name', header: 'class', size: 80 },
  {
    accessorKey: 'meas_counts',
    header: 'meas count',
    size: 96,
    cell: ({ row }) => row.original.meas_counts.toLocaleString()
  },
  {
    accessorKey: 'avg_meastime',
    header: 'avg meastime',
    size: 120,
    cell: ({ row }) => formatSecondsAsDuration(Math.round(row.original.avg_meastime))
  },
  {
    accessorKey: 'total_meastime',
    header: 'total TAT',
    size: 140,
    cell: ({ row }) => formatSecondsAsDuration(row.original.total_meastime)
  },
  {
    id: 'share',
    header: 'share',
    size: 72,
    cell: ({ row }) => {
      const total = totalForShare.value
      if (!total) return '0.00%'
      return `${(row.original.total_meastime / total * 100).toFixed(2)}%`
    }
  }
]

const exportFileName = computed(() => {
  const today = todayStamp()
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-${today}.csv`
})

const toast = useToast()

const rankingTable = () => {
  const headers = [
    'rank', 'full_name', 'class',
    'meas_count', 'avg_meastime_sec', 'total_meastime_sec',
    'share_pct'
  ]
  const total = totalForShare.value
  const rows = sortedRankingRows.value.map(r => [
    r.rank,
    r.full_name,
    r.class_name,
    r.meas_counts,
    r.avg_meastime,
    r.total_meastime,
    total ? (r.total_meastime / total * 100).toFixed(2) : '0.00'
  ])
  return { headers, rows }
}

const downloadRankingCsv = () => {
  const { headers, rows } = rankingTable()
  downloadCsv(exportFileName.value, headers, rows)
}

const copyRankingTable = async () => {
  const { headers, rows } = rankingTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
