<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Fail 이슈"
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
                : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'"
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
    <div
      v-if="viewMode === 'by-device'"
      class="dashboard-surface rounded-2xl px-3.5 py-2.5"
    >
      <div class="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            디바이스 선택
          </h3>
          <span class="text-[10.5px] text-zinc-400 dark:text-zinc-500">
            {{ filteredDeviceList.length }} / {{ deviceList.length }}개의 디바이스
          </span>
        </div>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-rotate-ccw"
          label="초기화"
          :disabled="!selectedLot && !lotSearch && selectedCategories.length === 0"
          @click="() => { selectedLot = null; lotSearch = ''; selectedCategories = [] }"
        />
      </div>

      <div
        v-if="categoryField && categoryOptions.length"
        class="mb-2 flex flex-wrap items-start gap-2 min-w-0"
      >
        <span class="mt-1.5 font-mono text-[10px] text-zinc-400 shrink-0">{{ categoryField }}</span>
        <div class="flex flex-wrap items-center gap-1 min-w-0">
          <button
            v-for="category in categoryOptions"
            :key="category"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
            :class="chipClass(selectedCategories.includes(category))"
            @click="toggleCategory(category)"
          >
            {{ category }}
          </button>
        </div>
      </div>

      <div class="flex flex-wrap items-start gap-2 min-w-0">
        <span class="mt-1.5 font-mono text-[10px] text-zinc-400 shrink-0">lot_cd</span>
        <UInput
          v-model="lotSearch"
          class="w-44 shrink-0"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-search"
          placeholder="디바이스 검색"
        />
        <div class="flex flex-wrap items-center gap-1 min-w-0">
          <button
            v-for="device in deviceChipStrip.chips"
            :key="device.lot_cd"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-md px-2 font-mono text-[11px] font-medium ring-1 transition-colors"
            :class="chipClass(selectedLot === device.lot_cd)"
            :title="`${device.exec_count.toLocaleString()} runs · align fails ${device.align_fail_count} · meas fails ${device.meas_fail_count}`"
            @click="toggleLot(device.lot_cd)"
          >
            {{ device.lot_cd }}
          </button>
          <span
            v-if="deviceChipStrip.overflowCount > 0"
            class="font-mono text-[10px] text-zinc-400 dark:text-zinc-500"
          >
            +{{ deviceChipStrip.overflowCount }}
          </span>
          <span
            v-if="!deviceList.length"
            class="text-[11px] text-zinc-400 dark:text-zinc-500"
          >
            이 기간에 측정된 디바이스가 없습니다.
          </span>
        </div>
      </div>
    </div>

    <!-- 디바이스별 mode without a selection: prompt -->
    <div
      v-if="viewMode === 'by-device' && !selectedLot"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-mouse-pointer-click"
        class="mx-auto h-6 w-6 text-zinc-400"
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
        class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="mx-auto h-5 w-5 animate-spin text-zinc-400"
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
          class="mx-auto h-6 w-6 text-zinc-400"
        />
        <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          No measurements in this range
        </p>
        <p class="mt-1 text-xs text-(--sk-ink-muted)">
          Try widening the date range or selecting a different fab.
        </p>
      </div>

      <template v-else>
        <!-- KPI cards: side-by-side Align / Meas -->
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-crosshair"
                  class="h-4 w-4 text-(--sk-bad)"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Align Fail
                </h3>
                <span class="text-[10.5px] text-zinc-400">wafer alignment outcome at run start</span>
              </div>
            </template>
            <div class="flex flex-wrap">
              <div
                v-for="(cell, i) in alignKpiCells"
                :key="cell.label"
                class="flex min-w-[160px] flex-1 flex-col gap-0.5 px-4 py-3"
                :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': i > 0 }"
              >
                <span
                  class="text-2xl font-bold leading-none tabular-nums"
                  :class="cell.tone"
                >{{ cell.value }}</span>
                <span class="text-[11px] text-(--sk-ink-muted)">{{ cell.label }}</span>
              </div>
            </div>
          </UCard>

          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-image-off"
                  class="h-4 w-4 text-(--sk-bad)"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Meas Fail
                </h3>
                <span class="text-[10.5px] text-zinc-400">
                  fail_ratio &gt; {{ formatPercent(measFailThreshold, 0) }}
                </span>
              </div>
            </template>
            <div class="flex flex-wrap">
              <div
                v-for="(cell, i) in measKpiCells"
                :key="cell.label"
                class="flex min-w-[160px] flex-1 flex-col gap-0.5 px-4 py-3"
                :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': i > 0 }"
              >
                <span
                  class="text-2xl font-bold leading-none tabular-nums"
                  :class="cell.tone"
                >{{ cell.value }}</span>
                <span class="text-[11px] text-(--sk-ink-muted)">{{ cell.label }}</span>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Trend charts -->
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Align fail · daily trend
                </h3>
              </div>
            </template>
            <div
              ref="alignTrendEl"
              class="h-[400px] w-full"
            />
          </UCard>

          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Meas fail · daily trend
                </h3>
              </div>
            </template>
            <div
              ref="measTrendEl"
              class="h-[400px] w-full"
            />
          </UCard>
        </div>

        <!-- Ranking tables -->
        <div class="grid grid-cols-1 gap-3 2xl:grid-cols-2">
          <!-- @vue-generic {FailIssueAlignRow} -->
          <EbeamFailIssueRankingTable
            title="Align fails by recipe"
            search-placeholder="Search recipe / class"
            :rows="alignRows"
            :columns="alignColumns"
            :sortable-ids="alignSortableIds"
            default-sort-id="align_fail_count"
            :reset-key="cacheKey"
            :search-predicate="alignSearchPredicate"
            @download="downloadAlignCsv"
          />
          <!-- @vue-generic {FailIssueMeasRow} -->
          <EbeamFailIssueRankingTable
            title="Meas fails by recipe"
            search-placeholder="Search recipe / class…"
            :rows="measRows"
            :columns="measColumns"
            :sortable-ids="measSortableIds"
            default-sort-id="meas_fail_count"
            :reset-key="cacheKey"
            :search-predicate="measSearchPredicate"
            @download="downloadMeasCsv"
          />
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatPercent,
  formatTimestamp,
  useFailIssueApi,
  type FailIssueAlignRow,
  type FailIssueMeasRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'
import { chipClass } from '~/utils/chipClass'
import { downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: FailIssueToolType
}>()

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)

// Empty means "let the server resolve its default window". Computing
// wall-clock today locally would drift past the mock's ANCHOR_TIME for
// long-running Flask processes — same convention as recipe-tat.
const userDateRange = ref({ start: '', end: '' })

const VIEW_MODES = [
  { value: 'summary', label: '전체 요약', icon: 'i-lucide-layers' },
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' }
] as const
type ViewMode = typeof VIEW_MODES[number]['value']

const viewMode = ref<ViewMode>('summary')
const metaSubtitle = computed(() =>
  viewMode.value === 'by-device'
    ? 'Align Fail / Measurement Fail을 디바이스별로 분석합니다.'
    : 'Align Fail / Measurement Fail을 Fab 기준으로 분석합니다.'
)
const selectedLot = ref<string | null>(null)
const lotSearch = ref('')
const selectedCategories = ref<string[]>([])

const DEVICE_CHIP_BUDGET = 24

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

const measFailThreshold = computed(() => summary.value?.meas_fail_threshold ?? 0.15)

// Pick the categorical attribute the picker should narrow by — R3 lots
// carry prod_catg_cd, M-fab lots carry tech_nm. (Same logic as recipe-tat.)
const categoryField = computed<'prod_catg_cd' | 'tech_nm' | null>(() => {
  const list = deviceList.value
  if (list.some(d => d.prod_catg_cd)) return 'prod_catg_cd'
  if (list.some(d => d.tech_nm)) return 'tech_nm'
  return null
})

const categoryOptions = computed(() => {
  const field = categoryField.value
  if (!field) return [] as string[]
  const set = new Set<string>()
  for (const d of deviceList.value) {
    const value = d[field]
    if (value) set.add(value)
  }
  return Array.from(set).sort()
})

const filteredDeviceList = computed(() => {
  const field = categoryField.value
  if (!field || selectedCategories.value.length === 0) return deviceList.value
  const allowed = new Set(selectedCategories.value)
  return deviceList.value.filter((d) => {
    const value = d[field]
    return value !== null && allowed.has(value)
  })
})

const deviceChipStrip = computed(() => {
  const q = lotSearch.value.trim().toLowerCase()
  const all = filteredDeviceList.value
  const matches = q
    ? all.filter(d => d.lot_cd.toLowerCase().includes(q))
    : all

  const visible = matches.slice(0, DEVICE_CHIP_BUDGET)
  const overflow = Math.max(0, matches.length - DEVICE_CHIP_BUDGET)

  const selected = selectedLot.value
  if (!selected || visible.some(d => d.lot_cd === selected)) {
    return { chips: visible, overflowCount: overflow }
  }

  const selectedRow = deviceList.value.find(d => d.lot_cd === selected)
  if (!selectedRow) {
    return { chips: visible, overflowCount: overflow }
  }

  const trimmed = visible.slice(0, DEVICE_CHIP_BUDGET - 1)
  return {
    chips: [selectedRow, ...trimmed],
    overflowCount: overflow + (visible.length - trimmed.length)
  }
})

const toggleLot = (lot: string) => {
  selectedLot.value = selectedLot.value === lot ? null : lot
}

const toggleCategory = (category: string) => {
  selectedCategories.value = selectedCategories.value.includes(category)
    ? selectedCategories.value.filter(c => c !== category)
    : [...selectedCategories.value, category]
}

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

// Clear selection on scope change so the rankings/summary don't keep
// filtering by a stale lot_cd that's invisible in the refetched picker.
watch(
  () => [props.fab, userDateRange.value.start, userDateRange.value.end],
  () => {
    if (selectedLot.value === null && lotSearch.value === '' && selectedCategories.value.length === 0) return
    selectedLot.value = null
    lotSearch.value = ''
    selectedCategories.value = []
  }
)

// KPI cells -----------------------------------------------------------------

const alignKpiCells = computed(() => {
  const s = summary.value
  if (!s) return placeholderKpis()
  return [
    { label: 'Align fails', value: s.align_fail_count.toLocaleString(), tone: 'text-(--sk-bad)' },
    { label: 'Fail rate', value: formatPercent(s.align_fail_rate), tone: 'text-zinc-900 dark:text-zinc-100' },
    { label: 'NA (skipped)', value: s.align_na_count.toLocaleString(), tone: 'text-zinc-600 dark:text-zinc-300' },
    { label: 'Distinct eqps', value: s.distinct_equipment.toLocaleString(), tone: 'text-zinc-700 dark:text-zinc-300' }
  ]
})

const measKpiCells = computed(() => {
  const s = summary.value
  if (!s) return placeholderKpis()
  return [
    { label: 'Meas fails', value: s.meas_fail_count.toLocaleString(), tone: 'text-(--sk-bad)' },
    { label: 'Fail rate', value: formatPercent(s.meas_fail_rate), tone: 'text-zinc-900 dark:text-zinc-100' },
    { label: 'Total runs', value: s.total_executions.toLocaleString(), tone: 'text-zinc-600 dark:text-zinc-300' },
    { label: 'Distinct recipes', value: s.distinct_recipes.toLocaleString(), tone: 'text-zinc-700 dark:text-zinc-300' }
  ]
})

function placeholderKpis() {
  return [
    { label: '—', value: '—', tone: 'text-(--sk-bad)' },
    { label: '—', value: '—', tone: 'text-zinc-900 dark:text-zinc-100' },
    { label: '—', value: '—', tone: 'text-zinc-600 dark:text-zinc-300' },
    { label: '—', value: '—', tone: 'text-zinc-700 dark:text-zinc-300' }
  ]
}

// Trend charts --------------------------------------------------------------
// One series per chart instead of stacking Align and Meas together. A single
// row can be both an align-fail and a meas-fail, so stacking would
// mis-represent totals. Two charts also keep the dashboard visually
// symmetric with the KPI strip above.

const alignTrendEl = ref<HTMLDivElement | null>(null)
const measTrendEl = ref<HTMLDivElement | null>(null)

const xAxisDates = computed(() => trendPoints.value.map(p => p.date))

const buildTrendOption = (
  seriesName: string,
  values: number[],
  color: string,
  baseline: number[]
): EChartsOption => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: unknown) => {
      const arr = Array.isArray(params) ? params : [params]
      const first = arr[0] as { dataIndex?: number }
      const idx = typeof first.dataIndex === 'number' ? first.dataIndex : 0
      const point = trendPoints.value[idx]
      if (!point) return ''
      return [
        `<b>${point.date}</b>`,
        `${seriesName}: <b>${values[idx]?.toLocaleString() ?? 0}</b>`,
        `Total executions: ${point.exec_count.toLocaleString()}`
      ].join('<br/>')
    }
  },
  legend: {
    data: [seriesName, 'Total runs'],
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
  yAxis: [
    {
      type: 'value',
      name: 'Fails',
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 }
    },
    {
      type: 'value',
      name: 'Runs',
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 },
      splitLine: { show: false }
    }
  ],
  series: [
    {
      name: seriesName,
      type: 'bar',
      data: values,
      itemStyle: { color, borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 14,
      yAxisIndex: 0
    },
    {
      name: 'Total runs',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: baseline,
      lineStyle: { color: '#a1a1aa', type: 'dashed', width: 1 },
      yAxisIndex: 1
    }
  ]
})

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
  { accessorKey: 'class_name', header: 'class', size: 70 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 200 },
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
  },
  {
    accessorKey: 'last_fail',
    header: 'last fail',
    size: 160,
    cell: ({ row }) => formatTimestamp(row.original.last_fail)
  }
]

const measColumns: TableColumn<FailIssueMeasRow>[] = [
  { accessorKey: 'rank', header: '#', size: 48 },
  { accessorKey: 'class_name', header: 'class', size: 70 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 200 },
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
  },
  {
    accessorKey: 'last_fail',
    header: 'last fail',
    size: 160,
    cell: ({ row }) => formatTimestamp(row.original.last_fail)
  }
]

// CSV downloads -------------------------------------------------------------

const exportFileBase = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const fab = (props.fab || 'all').toLowerCase()
  return `${props.toolType}-${fab}-fail-issue-${today}`
})

const downloadAlignCsv = (rows: FailIssueAlignRow[]) => {
  const headers = ['rank', 'class', 'recipe', 'exec_count', 'align_fail_count', 'align_fail_rate_pct', 'last_fail']
  const data = rows.map(r => [
    r.rank,
    r.class_name,
    r.recipe_name,
    r.exec_count,
    r.align_fail_count,
    (r.align_fail_rate * 100).toFixed(2),
    r.last_fail ?? ''
  ])
  downloadCsv(`${exportFileBase.value}-align.csv`, headers, data)
}

const downloadMeasCsv = (rows: FailIssueMeasRow[]) => {
  const headers = ['rank', 'class', 'recipe', 'exec_count', 'meas_fail_count', 'meas_fail_rate_pct', 'avg_fail_ratio_pct', 'last_fail']
  const data = rows.map(r => [
    r.rank,
    r.class_name,
    r.recipe_name,
    r.exec_count,
    r.meas_fail_count,
    (r.meas_fail_rate * 100).toFixed(2),
    (r.avg_fail_ratio * 100).toFixed(2),
    r.last_fail ?? ''
  ])
  downloadCsv(`${exportFileBase.value}-meas.csv`, headers, data)
}
</script>
