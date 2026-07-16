<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="identity"
      :title="viewTitle"
      :subtitle="metaSubtitle"
      :as-of="summary?.anchor_date"
      cadence="1시간 주기"
    >
      <template #toggle>
        <div class="flex flex-wrap items-center gap-2.5">
          <div
            role="radiogroup"
            class="inline-flex items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
          >
            <button
              v-for="mode in VIEW_MODES"
              :key="mode.value"
              type="button"
              role="radio"
              :aria-checked="viewMode === mode.value"
              class="inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors"
              :class="viewMode === mode.value
                ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
                : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="viewMode = mode.value"
            >
              <UIcon
                :name="mode.icon"
                class="h-4 w-4"
              />
              {{ mode.label }}
            </button>
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
    </EbeamMetaBar>

    <!-- Device picker (디바이스별 mode only) -->
    <EbeamAnalyticsDevicePicker
      v-if="viewMode === 'by-device'"
      v-model:selected-lot="selectedLot"
      :devices="deviceList"
      :get-title="failDeviceTitle"
      :reset-key="devicesCacheKey"
    />

    <!-- 디바이스별 mode without a selection: prompt -->
    <div
      v-if="viewMode === 'by-device' && !selectedLot"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-mouse-pointer-click"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        디바이스를 선택해주세요
      </p>
      <p class="mt-1 text-xs text-(--sk-ink-muted)">
        위에서 디바이스 칩을 클릭하면 해당 디바이스의 Fail 이슈 정보가 표시됩니다.
      </p>
    </div>

    <template v-else>
      <div
        v-if="status === 'pending' && !alignRows.length && !measRows.length"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center sk-body"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
        />
        <p class="mt-2">
          Loading fail-issue data…
        </p>
      </div>
      <div
        v-else-if="!summary?.total_executions"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-inbox"
          class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
        />
        <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          No measurements in this range
        </p>
        <p class="mt-1 text-xs text-(--sk-ink-muted)">
          Try widening the date range or selecting a different fab.
        </p>
      </div>

      <template v-else>
        <!-- Trend chart for the active aspect -->
        <UCard
          v-if="showAlign"
          class="dashboard-surface rounded-2xl"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="sk-title">
                  Align fail · daily trend
                </h3>
              </div>
              <div
                role="radiogroup"
                aria-label="Align fail chart type"
                class="inline-flex items-center gap-0.5 rounded-md bg-zinc-100/80 p-0.5 dark:bg-zinc-800/70"
              >
                <button
                  v-for="chartOption in CHART_TYPES"
                  :key="chartOption.value"
                  type="button"
                  role="radio"
                  :aria-checked="chartType === chartOption.value"
                  class="inline-flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition-colors"
                  :class="chartType === chartOption.value
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50'
                    : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
                  @click="chartType = chartOption.value"
                >
                  <UIcon
                    :name="chartOption.icon"
                    class="h-3.5 w-3.5"
                  />
                  {{ chartOption.label }}
                </button>
              </div>
            </div>
          </template>
          <div
            ref="alignTrendEl"
            class="h-[400px] w-full"
          />
        </UCard>

        <UCard
          v-if="showMeas"
          class="dashboard-surface rounded-2xl"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="sk-title">
                  Meas fail · daily trend
                </h3>
              </div>
              <div
                role="radiogroup"
                aria-label="Meas fail chart type"
                class="inline-flex items-center gap-0.5 rounded-md bg-zinc-100/80 p-0.5 dark:bg-zinc-800/70"
              >
                <button
                  v-for="chartOption in CHART_TYPES"
                  :key="chartOption.value"
                  type="button"
                  role="radio"
                  :aria-checked="chartType === chartOption.value"
                  class="inline-flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition-colors"
                  :class="chartType === chartOption.value
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50'
                    : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
                  @click="chartType = chartOption.value"
                >
                  <UIcon
                    :name="chartOption.icon"
                    class="h-3.5 w-3.5"
                  />
                  {{ chartOption.label }}
                </button>
              </div>
            </div>
          </template>
          <div
            ref="measTrendEl"
            class="h-[400px] w-full"
          />
        </UCard>

        <!-- Ranking table for the active aspect -->
        <!-- @vue-generic {FailIssueAlignRow} -->
        <EbeamFailIssueRankingTable
          v-if="showAlign"
          title="Align fails by recipe"
          search-placeholder="Search recipe / class"
          :summary-items="alignSummaryItems"
          :rows="alignRows"
          :columns="alignColumns"
          :sortable-ids="alignSortableIds"
          default-sort-id="align_fail_count"
          :reset-key="cacheKey"
          :search-predicate="alignSearchPredicate"
          @download="downloadAlignCsv"
          @copy="copyAlignTable"
        >
          <template #actions-cell="{ row }">
            <EbeamRecipeRowActions
              :tool-type="toolType"
              :fab="fab"
              :recipe-name="row.original.recipe_name"
            />
          </template>
        </EbeamFailIssueRankingTable>
        <!-- @vue-generic {FailIssueMeasRow} -->
        <EbeamFailIssueRankingTable
          v-if="showMeas"
          title="Meas fails by recipe"
          search-placeholder="Search recipe / class…"
          :summary-items="measSummaryItems"
          :rows="measRows"
          :columns="measColumns"
          :sortable-ids="measSortableIds"
          default-sort-id="meas_fail_count"
          :reset-key="cacheKey"
          :search-predicate="measSearchPredicate"
          @download="downloadMeasCsv"
          @copy="copyMeasTable"
        >
          <template #actions-cell="{ row }">
            <EbeamRecipeRowActions
              :tool-type="toolType"
              :fab="fab"
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
import {
  formatPercent,
  useFailIssueApi,
  type FailIssueAlignRow,
  type FailIssueDeviceRow,
  type FailIssueMeasRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { buildFailSummaryItems } from '~/utils/recipeStatusSummary'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: FailIssueToolType
  // Which failure aspect to render — the merged Recipe 현황 page shows each
  // as its own tab on one shared instance (data + filters survive flips).
  section: 'align' | 'meas'
}>()

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)
const showAlign = computed(() => props.section === 'align')
const showMeas = computed(() => props.section === 'meas')
const viewTitle = computed(() => props.section === 'align' ? 'Align Fail' : 'Meas Fail')

// Empty means "let the server resolve its default window". Computing
// wall-clock today locally would drift past the mock's ANCHOR_TIME for
// long-running Flask processes — same convention as recipe-tat.
const userDateRange = ref({ start: '', end: '' })

const VIEW_MODES = [
  { value: 'summary', label: '전체 요약', icon: 'i-lucide-layers' },
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' }
] as const
type ViewMode = typeof VIEW_MODES[number]['value']

const CHART_TYPES = [
  { value: 'bar', label: 'Bar', icon: 'i-lucide-chart-column' },
  { value: 'line', label: 'Line', icon: 'i-lucide-chart-no-axes-combined' },
  { value: 'ratio', label: 'Ratio', icon: 'i-lucide-percent' }
] as const
type ChartType = typeof CHART_TYPES[number]['value']

const viewMode = ref<ViewMode>('summary')
const chartType = ref<ChartType>('bar')
const metaSubtitle = computed(() => {
  const aspect = props.section === 'align' ? 'Align Fail' : 'Measurement Fail'
  return viewMode.value === 'by-device'
    ? `${aspect}을 디바이스별로 분석합니다.`
    : `${aspect}을 Fab 기준으로 분석합니다.`
})
const selectedLot = ref<string | null>(null)

const {
  fetchSummary,
  fetchDailyTrend,
  fetchAlignRanking,
  fetchMeasRanking,
  fetchDevices
} = useFailIssueApi()

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabId: props.fab || undefined,
  startDate: userDateRange.value.start || undefined,
  endDate: userDateRange.value.end || undefined,
  limit: 1000,
  lotCd: viewMode.value === 'by-device' ? (selectedLot.value ?? undefined) : undefined
}))

const cacheKey = computed(
  () => `fail-issue:${queryParams.value.toolType}:${queryParams.value.fabId ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
    + `:${queryParams.value.lotCd ?? '*'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  async () => {
    const [summary, daily, align, meas] = await Promise.all([
      fetchSummary(queryParams.value),
      fetchDailyTrend(queryParams.value),
      fetchAlignRanking(queryParams.value),
      fetchMeasRanking(queryParams.value)
    ])
    return { summary, daily, align, meas }
  },
  { watch: [cacheKey] }
)

// Devices fetch excludes lot_cd from its cache key — this endpoint is the
// source of truth for which lot_cds exist in scope, so a current selection
// must not filter the picker itself.
const devicesCacheKey = computed(
  () => `fail-issue-devices:${queryParams.value.toolType}:${queryParams.value.fabId ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)
const { data: devicesData } = await useAsyncData(
  () => devicesCacheKey.value,
  () => fetchDevices(queryParams.value),
  { watch: [devicesCacheKey] }
)

const summary = computed(() => data.value?.summary)
const trendPoints = computed(() => data.value?.daily.points ?? [])
const alignRows = computed<FailIssueAlignRow[]>(() => data.value?.align.rows ?? [])
const measRows = computed<FailIssueMeasRow[]>(() => data.value?.meas.rows ?? [])
const deviceList = computed(() => devicesData.value?.devices ?? [])
const failDeviceTitle = (device: FailIssueDeviceRow) =>
  `전체 측정 장수 ${device.exec_count.toLocaleString()} · align fails ${device.align_fail_count} · meas fails ${device.meas_fail_count}`

// Echo the server-resolved window only inside the getter (vs. mirroring
// into a ref) so first-load values don't trigger a redundant refetch.
const dateRange = computed({
  get: () => {
    if (userDateRange.value.start && userDateRange.value.end) {
      return userDateRange.value
    }
    return {
      start: summary.value?.start_date ?? '',
      end: summary.value?.end_date ?? ''
    }
  },
  set: (next) => {
    userDateRange.value = next
  }
})

const alignSummaryItems = computed(() => buildFailSummaryItems({
  failLabel: 'Align fails',
  failCount: summary.value?.align_fail_count.toLocaleString() ?? '—',
  totalMeasurements: summary.value?.total_executions.toLocaleString() ?? '—',
  failRatio: summary.value ? formatPercent(summary.value.align_fail_rate) : '—'
}))

const measSummaryItems = computed(() => buildFailSummaryItems({
  failLabel: 'Meas fails',
  failCount: summary.value?.meas_fail_count.toLocaleString() ?? '—',
  totalMeasurements: summary.value?.total_executions.toLocaleString() ?? '—',
  failRatio: summary.value ? formatPercent(summary.value.meas_fail_rate) : '—'
}))

// Trend charts --------------------------------------------------------------
// One series per chart instead of stacking Align and Meas together. A single
// row can be both an align-fail and a meas-fail, so stacking would
// mis-represent totals.

const alignTrendEl = ref<HTMLDivElement | null>(null)
const measTrendEl = ref<HTMLDivElement | null>(null)

const xAxisDates = computed(() => trendPoints.value.map(p => p.date))

const buildTrendOption = (
  seriesName: string,
  values: number[],
  color: string,
  baseline: number[]
): EChartsOption => {
  const totalLabel = '전체 측정 장수'
  const isRatio = chartType.value === 'ratio'
  const ratioSeriesName = `${seriesName} ratio`
  const ratioValues = values.map((value, index) => {
    const total = baseline[index] ?? 0
    return total > 0 ? value / total * 100 : 0
  })

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as { dataIndex?: number }
        const idx = typeof first.dataIndex === 'number' ? first.dataIndex : 0
        const point = trendPoints.value[idx]
        if (!point) return ''
        const failCount = values[idx] ?? 0
        const totalCount = baseline[idx] ?? 0
        return [
          `<b>${point.date}</b>`,
          isRatio
            ? `${ratioSeriesName}: <b>${formatPercent(totalCount > 0 ? failCount / totalCount : 0)}</b>`
            : `${seriesName}: <b>${failCount.toLocaleString()}</b>`,
          `${totalLabel}: ${totalCount.toLocaleString()}`
        ].join('<br/>')
      }
    },
    legend: {
      data: isRatio ? [ratioSeriesName] : [seriesName, totalLabel],
      bottom: 0,
      textStyle: { fontSize: 10 }
    },
    grid: { left: 8, right: 16, top: 12, bottom: 32, containLabel: true },
    xAxis: {
      type: 'category',
      data: xAxisDates.value,
      axisLabel: {
        fontSize: 10,
        interval: Math.max(0, Math.floor(xAxisDates.value.length / 8) - 1)
      }
    },
    yAxis: isRatio
      ? {
          type: 'value',
          name: 'Fail rate',
          nameTextStyle: { fontSize: 10 },
          axisLabel: { fontSize: 10, formatter: '{value}%' }
        }
      : [
          {
            type: 'value',
            name: 'Fails',
            nameTextStyle: { fontSize: 10 },
            axisLabel: { fontSize: 10 }
          },
          {
            type: 'value',
            name: '측정 장수',
            nameTextStyle: { fontSize: 10 },
            axisLabel: { fontSize: 10 },
            splitLine: { show: false }
          }
        ],
    series: isRatio
      ? [{
          name: ratioSeriesName,
          type: 'line',
          data: ratioValues,
          smooth: true,
          showSymbol: false,
          lineStyle: { color, width: 2 },
          itemStyle: { color },
          areaStyle: { color, opacity: 0.08 }
        }]
      : [
          chartType.value === 'bar'
            ? {
                name: seriesName,
                type: 'bar',
                data: values,
                itemStyle: { color, borderRadius: [4, 4, 0, 0] },
                barMaxWidth: 14,
                yAxisIndex: 0
              }
            : {
                name: seriesName,
                type: 'line',
                data: values,
                smooth: true,
                showSymbol: false,
                lineStyle: { color, width: 2 },
                itemStyle: { color },
                areaStyle: { color, opacity: 0.08 },
                yAxisIndex: 0
              },
          {
            name: totalLabel,
            type: 'line',
            smooth: true,
            symbol: 'none',
            data: baseline,
            lineStyle: { color: '#a1a1aa', type: 'dashed', width: 1 },
            yAxisIndex: 1
          }
        ]
  }
}

const alignTrendOption = computed<EChartsOption>(() =>
  buildTrendOption(
    'Align fails',
    trendPoints.value.map(p => p.align_fail_count),
    '#ef4444',
    trendPoints.value.map(p => p.exec_count)
  ))

const measTrendOption = computed<EChartsOption>(() =>
  buildTrendOption(
    'Meas fails',
    trendPoints.value.map(p => p.meas_fail_count),
    '#f59e0b',
    trendPoints.value.map(p => p.exec_count)
  ))

useEchart(alignTrendEl, alignTrendOption)
useEchart(measTrendEl, measTrendOption)

// Ranking table configs -----------------------------------------------------

const alignSortableIds = ['exec_count', 'align_fail_count', 'align_fail_rate'] as const
const measSortableIds = ['exec_count', 'meas_fail_count', 'meas_fail_rate', 'avg_fail_ratio'] as const

const alignSearchPredicate = (row: FailIssueAlignRow, q: string) =>
  row.recipe_name.toLowerCase().includes(q)
  || row.class_name.toLowerCase().includes(q)
  || row.full_name.toLowerCase().includes(q)

const measSearchPredicate = (row: FailIssueMeasRow, q: string) =>
  row.recipe_name.toLowerCase().includes(q)
  || row.class_name.toLowerCase().includes(q)
  || row.full_name.toLowerCase().includes(q)

const alignColumns: TableColumn<FailIssueAlignRow>[] = [
  { accessorKey: 'rank', header: '#', size: 48 },
  { accessorKey: 'full_name', header: 'full name', size: 220 },
  { id: 'actions', header: '', size: 96 },
  { accessorKey: 'class_name', header: 'class', size: 70 },
  {
    accessorKey: 'exec_count',
    header: 'runs',
    size: 80,
    cell: ({ row }) => row.original.exec_count.toLocaleString()
  },
  {
    accessorKey: 'align_fail_count',
    header: 'fails',
    size: 80,
    cell: ({ row }) => row.original.align_fail_count.toLocaleString()
  },
  {
    accessorKey: 'align_fail_rate',
    header: 'rate',
    size: 80,
    cell: ({ row }) => formatPercent(row.original.align_fail_rate)
  }
]

const measColumns: TableColumn<FailIssueMeasRow>[] = [
  { accessorKey: 'rank', header: '#', size: 48 },
  { accessorKey: 'full_name', header: 'full name', size: 220 },
  { id: 'actions', header: '', size: 96 },
  { accessorKey: 'class_name', header: 'class', size: 70 },
  {
    accessorKey: 'exec_count',
    header: 'runs',
    size: 80,
    cell: ({ row }) => row.original.exec_count.toLocaleString()
  },
  {
    accessorKey: 'meas_fail_count',
    header: 'fails',
    size: 80,
    cell: ({ row }) => row.original.meas_fail_count.toLocaleString()
  },
  {
    accessorKey: 'meas_fail_rate',
    header: 'rate',
    size: 80,
    cell: ({ row }) => formatPercent(row.original.meas_fail_rate)
  },
  {
    accessorKey: 'avg_fail_ratio',
    header: 'avg ratio',
    size: 90,
    cell: ({ row }) => formatPercent(row.original.avg_fail_ratio)
  }
]

// CSV downloads -------------------------------------------------------------

const exportFileBase = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const fab = (props.fab || 'all').toLowerCase()
  return `${props.toolType}-${fab}-fail-issue-${today}`
})

const toast = useToast()

const notifyCopy = (ok: boolean) => {
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const alignTable = (rows: FailIssueAlignRow[]) => ({
  headers: ['rank', 'full_name', 'class', 'exec_count', 'align_fail_count', 'align_fail_rate_pct'],
  data: rows.map(r => [
    r.rank,
    r.full_name,
    r.class_name,
    r.exec_count,
    r.align_fail_count,
    (r.align_fail_rate * 100).toFixed(2)
  ])
})

const measTable = (rows: FailIssueMeasRow[]) => ({
  headers: ['rank', 'full_name', 'class', 'exec_count', 'meas_fail_count', 'meas_fail_rate_pct', 'avg_fail_ratio_pct'],
  data: rows.map(r => [
    r.rank,
    r.full_name,
    r.class_name,
    r.exec_count,
    r.meas_fail_count,
    (r.meas_fail_rate * 100).toFixed(2),
    (r.avg_fail_ratio * 100).toFixed(2)
  ])
})

const downloadAlignCsv = (rows: FailIssueAlignRow[]) => {
  const { headers, data } = alignTable(rows)
  downloadCsv(`${exportFileBase.value}-align.csv`, headers, data)
}

const downloadMeasCsv = (rows: FailIssueMeasRow[]) => {
  const { headers, data } = measTable(rows)
  downloadCsv(`${exportFileBase.value}-meas.csv`, headers, data)
}

const copyAlignTable = async (rows: FailIssueAlignRow[]) => {
  const { headers, data } = alignTable(rows)
  notifyCopy(await copyTableToClipboard(headers, data))
}

const copyMeasTable = async (rows: FailIssueMeasRow[]) => {
  const { headers, data } = measTable(rows)
  notifyCopy(await copyTableToClipboard(headers, data))
}
</script>
