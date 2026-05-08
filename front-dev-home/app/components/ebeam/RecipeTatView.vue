<template>
  <div class="space-y-3">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <div class="min-w-0">
          <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            {{ toolLabel }}
          </p>
          <h1 class="text-2xl font-bold whitespace-nowrap text-zinc-950 dark:text-zinc-50">
            Recipe TAT
          </h1>
        </div>
        <div class="hidden h-9 w-px self-end mb-1 bg-zinc-200 dark:bg-zinc-700 md:block" />
        <span class="self-end mb-2 inline-flex h-6 items-center gap-1 rounded-md bg-zinc-100 px-2 font-mono text-[11px] font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
          <UIcon
            name="i-lucide-factory"
            class="h-3 w-3"
          /> {{ fab || '—' }}
        </span>
      </div>

      <div class="flex items-center gap-2 self-start md:self-auto">
        <EbeamDateRangePopover
          v-model="dateRange"
          :anchor-date="summary?.anchor_date"
        />
      </div>
    </div>

    <!-- View mode toggle -->
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
            {{ deviceList.length }}개의 디바이스
          </span>
        </div>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-rotate-ccw"
          label="초기화"
          :disabled="!selectedLot"
          @click="selectedLot = null"
        />
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
            :title="`${device.exec_count.toLocaleString()} runs · ${formatSecondsCompact(device.total_meastime)}`"
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

    <!-- 디바이스별 mode without a selection: prompt instead of dashboard -->
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
      <p class="mt-1 text-xs text-zinc-500">
        위에서 디바이스 칩을 클릭하면 해당 디바이스의 Recipe TAT 정보가 표시됩니다.
      </p>
    </div>

    <template v-else>
      <!-- KPI strip -->
    <div class="dashboard-surface flex flex-wrap rounded-2xl">
      <div
        v-for="(cell, index) in kpiCells"
        :key="cell.label"
        class="flex min-w-[160px] flex-1 flex-col gap-0.5 px-4 py-3"
        :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }"
      >
        <span
          class="text-2xl font-bold leading-none tabular-nums"
          :class="cell.tone"
        >{{ cell.value }}</span>
        <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
      </div>
    </div>

    <!-- Empty / loading state -->
    <div
      v-if="status === 'pending' && !rankingRows.length"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        Loading recipe TAT…
      </p>
    </div>
    <div
      v-else-if="!rankingRows.length"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-inbox"
        class="mx-auto h-6 w-6 text-zinc-400"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        No measurements in this range
      </p>
      <p class="mt-1 text-xs text-zinc-500">
        Try widening the date range or selecting a different fab.
      </p>
    </div>

    <template v-else>
      <!-- Charts -->
      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <UCard class="dashboard-surface rounded-2xl">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-bar-chart-horizontal"
                  class="h-4 w-4 text-zinc-500"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Top {{ topNLimit }} recipes by total TAT
                </h3>
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
            class="h-[420px] w-full"
          />
        </UCard>

        <UCard class="dashboard-surface rounded-2xl">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-trending-up"
                class="h-4 w-4 text-zinc-500"
              />
              <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Daily TAT trend
              </h3>
            </div>
          </template>
          <div
            ref="trendEl"
            class="h-[420px] w-full"
          />
        </UCard>
      </div>

      <!-- Table -->
      <div class="dashboard-surface rounded-2xl px-3.5 py-3">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              Ranked recipes
            </h3>
            <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {{ filteredRankingRows.length.toLocaleString() }} / {{ rankingRows.length.toLocaleString() }}
            </span>
            <span
              v-if="rankingLimit && rankingRows.length >= rankingLimit"
              class="font-mono text-[10px] text-amber-600 dark:text-amber-400"
            >capped at {{ rankingLimit.toLocaleString() }}</span>
          </div>
          <div class="flex items-center gap-2">
            <UInput
              v-model="tableSearch"
              size="xs"
              placeholder="Search recipe / class…"
              icon="i-lucide-search"
              class="w-[14rem]"
            />
            <USelect
              v-model="pageSize"
              class="w-[6.5rem]"
              size="xs"
              :items="pageSizeOptions"
            />
          </div>
        </div>

        <UTable
          :columns="columns"
          :data="pagedRows"
          sticky="header"
          :ui="tableUi"
        />

        <div class="mt-2 flex items-center justify-between text-xs text-zinc-500">
          <span class="tabular-nums">
            Page {{ currentPage }} / {{ pageCount }}
            <span class="ml-2 text-zinc-400">
              {{ pageStart }}–{{ pageEnd }} of {{ filteredRankingRows.length.toLocaleString() }}
            </span>
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
  type RecipeTatRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: RecipeTatToolType
}>()

// Empty so the first request inherits the server's default; computing
// "today" locally would drift past the mock's ANCHOR_TIME for long-running
// Flask processes. The watcher below mirrors the resolved window back.
const dateRange = ref({ start: '', end: '' })

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
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' }
] as const
type ViewMode = typeof VIEW_MODES[number]['value']

const viewMode = ref<ViewMode>('summary')
const selectedLot = ref<string | null>(null)
const lotSearch = ref('')

const DEVICE_CHIP_BUDGET = 24

const {
  fetchRecipeTatRanking,
  fetchRecipeTatSummary,
  fetchRecipeTatDailyTrend,
  fetchRecipeTatDevices
} = useRecipeTatApi()

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabId: props.fab || undefined,
  startDate: dateRange.value.start || undefined,
  endDate: dateRange.value.end || undefined,
  limit: 1000,
  lotCd: viewMode.value === 'by-device' ? (selectedLot.value ?? undefined) : undefined
}))

// `auto` placeholder keeps the cache key stable while the server resolves
// the default window on first fetch.
const cacheKey = computed(
  () => `recipe-tat:${queryParams.value.toolType}:${queryParams.value.fabId ?? 'ALL'}`
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
  () => `recipe-tat-devices:${queryParams.value.toolType}:${queryParams.value.fabId ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)
const { data: devicesData } = await useAsyncData(
  () => devicesCacheKey.value,
  () => fetchRecipeTatDevices(queryParams.value),
  { watch: [devicesCacheKey] }
)

const chipClass = (active: boolean) => active
  ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
  : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'

const deviceList = computed(() => devicesData.value?.devices ?? [])

// Pin the selected chip at the front so it never disappears behind a
// search filter or the +N overflow indicator.
const deviceChipStrip = computed(() => {
  const q = lotSearch.value.trim().toLowerCase()
  const all = deviceList.value
  const matches = q
    ? all.filter(d => d.lot_cd.toLowerCase().includes(q))
    : all

  const selectedRow = selectedLot.value
    ? all.find(d => d.lot_cd === selectedLot.value) ?? null
    : null
  const matchesWithoutSelected = matches.filter(d => d.lot_cd !== selectedLot.value)

  const remainingBudget = Math.max(0, DEVICE_CHIP_BUDGET - (selectedRow ? 1 : 0))
  const visibleMatches = matchesWithoutSelected.slice(0, remainingBudget)

  return {
    chips: selectedRow ? [selectedRow, ...visibleMatches] : visibleMatches,
    overflowCount: Math.max(0, matchesWithoutSelected.length - remainingBudget)
  }
})

const toggleLot = (lot: string) => {
  selectedLot.value = selectedLot.value === lot ? null : lot
}

const rankingRows = computed<RecipeTatRow[]>(() => data.value?.ranking.rows ?? [])
const rankingLimit = computed(() => data.value?.ranking.limit ?? 0)
const summary = computed(() => data.value?.summary)
const trendPoints = computed(() => data.value?.daily.points ?? [])

// Mirror the server-resolved window into `dateRange` so the popover has
// concrete values; equality guard prevents an extra refetch.
watch(data, (next) => {
  if (!next) return
  const start = next.summary.start_date
  const end = next.summary.end_date
  if (!start || !end) return
  if (dateRange.value.start === start && dateRange.value.end === end) return
  dateRange.value = { start, end }
}, { immediate: true })

// Clear selection on scope change — without this, ranking/summary/daily-trend
// keep filtering by a stale lot_cd that's invisible in the refetched picker,
// silently producing empty / misleading numbers.
watch(
  () => [props.fab, dateRange.value.start, dateRange.value.end],
  () => {
    if (selectedLot.value === null && lotSearch.value === '') return
    selectedLot.value = null
    lotSearch.value = ''
  }
)

// KPI cells

const kpiCells = computed(() => [
  {
    label: 'Total TAT',
    value: summary.value ? formatSecondsAsDuration(summary.value.total_tat_seconds) : '—',
    tone: 'text-(--sk-accent)'
  },
  {
    label: 'Distinct recipes',
    value: summary.value ? summary.value.total_recipes.toLocaleString() : '—',
    tone: 'text-zinc-900 dark:text-zinc-100'
  },
  {
    label: 'Total executions',
    value: summary.value ? summary.value.total_executions.toLocaleString() : '—',
    tone: 'text-zinc-900 dark:text-zinc-100'
  },
  {
    label: 'Avg meastime',
    value: summary.value ? formatSecondsAsDuration(Math.round(summary.value.avg_meastime)) : '—',
    tone: 'text-zinc-700 dark:text-zinc-300'
  }
])

// Bar chart — top N recipes by total TAT (horizontal)

const barEl = ref<HTMLDivElement | null>(null)

const barOption = computed<EChartsOption>(() => {
  const top = rankingRows.value.slice(0, topNLimit.value)
  // ECharts horizontal bar — categories on yAxis must read top-to-bottom,
  // so reverse the slice (largest at the top of the chart).
  const reversed = [...top].reverse()

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
    grid: { left: 8, right: 24, top: 8, bottom: 24, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        formatter: (v: number) => formatSecondsCompact(v)
      }
    },
    yAxis: {
      type: 'category',
      data: reversed.map(r => r.full_name),
      axisLabel: { fontSize: 10 }
    },
    series: [{
      type: 'bar',
      data: reversed.map(r => r.total_meastime),
      barMaxWidth: 18,
      itemStyle: { borderRadius: [0, 4, 4, 0] }
    }]
  }
})

useEchart(barEl, barOption)

// Daily trend line

const trendEl = ref<HTMLDivElement | null>(null)

const trendOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: unknown) => {
      const arr = Array.isArray(params) ? params : [params]
      const first = arr[0] as { name?: string, dataIndex?: number }
      const idx = typeof first.dataIndex === 'number' ? first.dataIndex : 0
      const point = trendPoints.value[idx]
      if (!point) return ''
      return [
        `<b>${point.date}</b>`,
        `Total TAT: ${formatSecondsAsDuration(point.total_meastime)}`,
        `Executions: ${point.exec_count.toLocaleString()}`
      ].join('<br/>')
    }
  },
  grid: { left: 8, right: 16, top: 12, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: trendPoints.value.map(p => p.date),
    axisLabel: {
      fontSize: 10,
      interval: Math.max(0, Math.floor(trendPoints.value.length / 8) - 1)
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
    areaStyle: { opacity: 0.18 },
    data: trendPoints.value.map(p => p.total_meastime)
  }]
}))

useEchart(trendEl, trendOption)

// Table

const tableSearch = ref('')
const pageSize = ref('25')
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const currentPage = ref(1)

const pageSizeOptions = [
  { label: '25 / page', value: '25' },
  { label: '50 / page', value: '50' },
  { label: '100 / page', value: '100' }
]

const filteredRankingRows = computed(() => {
  const q = tableSearch.value.trim().toLowerCase()
  if (!q) return rankingRows.value
  return rankingRows.value.filter(row =>
    row.recipe_name.toLowerCase().includes(q)
    || row.class_name.toLowerCase().includes(q)
    || row.full_name.toLowerCase().includes(q))
})

const pageCount = computed(
  () => Math.max(1, Math.ceil(filteredRankingRows.value.length / pageSizeNumber.value))
)
const pageStart = computed(
  () => filteredRankingRows.value.length === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1
)
const pageEnd = computed(
  () => Math.min(currentPage.value * pageSizeNumber.value, filteredRankingRows.value.length)
)

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSizeNumber.value
  return filteredRankingRows.value.slice(start, start + pageSizeNumber.value)
})

watch([tableSearch, pageSize, cacheKey], () => {
  currentPage.value = 1
})

const totalForShare = computed(
  () => rankingRows.value.reduce((sum, row) => sum + row.total_meastime, 0)
)

const columns: TableColumn<RecipeTatRow>[] = [
  { accessorKey: 'rank', header: '#', size: 56 },
  { accessorKey: 'class_name', header: 'class', size: 80 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 220 },
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
    accessorKey: 'last_run',
    header: 'last run',
    size: 160,
    cell: ({ row }) => row.original.last_run.replace('T', ' ').replace('Z', '')
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

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums',
  th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
