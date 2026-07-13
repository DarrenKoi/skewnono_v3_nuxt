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
    <div
      v-if="viewMode === 'by-device'"
      class="dashboard-surface rounded-2xl px-3.5 py-2.5"
    >
      <div class="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            디바이스 선택
          </h3>
          <span class="text-[10.5px] text-(--sk-ink-muted)">
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
        <span class="mt-1.5 font-mono text-[10px] text-(--sk-ink-muted) shrink-0">{{ categoryField }}</span>
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
        <span class="mt-1.5 font-mono text-[10px] text-(--sk-ink-muted) shrink-0">lot_cd</span>
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
            class="font-mono text-[10px] text-(--sk-ink-muted)"
          >
            +{{ deviceChipStrip.overflowCount }}
          </span>
          <span
            v-if="!deviceList.length"
            class="text-[11px] text-(--sk-ink-muted)"
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
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        디바이스를 선택해주세요
      </p>
      <p class="mt-1 text-xs text-(--sk-ink-muted)">
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
          <span class="text-[11px] text-(--sk-ink-muted)">{{ cell.label }}</span>
        </div>
      </div>

      <!-- Empty / loading state -->
      <div
        v-if="status === 'pending' && !rankingRows.length"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
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
        <!-- Charts -->
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <UIcon
                    name="i-lucide-bar-chart-horizontal"
                    class="h-4 w-4 text-(--sk-ink-muted)"
                  />
                  <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {{ barChartTitle }}
                  </h3>
                  <span
                    v-if="tableSearch.trim()"
                    class="text-[10.5px] text-(--sk-ink-muted)"
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

          <UCard class="dashboard-surface rounded-2xl">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-trending-up"
                  class="h-4 w-4 text-(--sk-ink-muted)"
                />
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
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
              <UButton
                size="xs"
                color="neutral"
                variant="outline"
                icon="i-lucide-download"
                label="CSV 다운로드"
                :disabled="sortedRankingRows.length === 0"
                @click="downloadRankingCsv"
              />
            </div>
          </div>

          <UTable
            v-model:sorting="sorting"
            :columns="columns"
            :data="pagedRows"
            :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
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
          </UTable>

          <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
            <span class="tabular-nums">
              Page {{ currentPage }} / {{ pageCount }}
              <span class="ml-2 text-(--sk-ink-muted)">
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
import type { SortingState } from '@tanstack/vue-table'
import {
  formatSecondsAsDuration,
  formatSecondsCompact,
  useRecipeTatApi,
  type RecipeTatRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'
import { chipClass } from '~/utils/chipClass'
import { downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: RecipeTatToolType
}>()

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)

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
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' }
] as const
type ViewMode = typeof VIEW_MODES[number]['value']

const viewMode = ref<ViewMode>('summary')
const metaSubtitle = computed(() =>
  viewMode.value === 'by-device'
    ? 'Recipe별 측정 시간 (TAT) 디바이스별로 분석합니다.'
    : 'Recipe별 측정 시간 (TAT)을 Fab 기준으로 분석합니다.'
)
const selectedLot = ref<string | null>(null)
const lotSearch = ref('')
const selectedCategories = ref<string[]>([])

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
  startDate: userDateRange.value.start || undefined,
  endDate: userDateRange.value.end || undefined,
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

const deviceList = computed(() => devicesData.value?.devices ?? [])

// Pick the categorical attribute the picker should narrow by — R3 lots
// carry prod_catg_cd, M-fab lots carry tech_nm. Whichever field has any
// values in the current device list wins.
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

// Stable chip order. Only pin the selection at the front if it would
// otherwise be hidden — i.e. it doesn't match the active search/category
// filter or fell past the visible budget. Pinning unconditionally would
// reshuffle the strip on every click and feel jumpy.
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

const rankingRows = computed<RecipeTatRow[]>(() => data.value?.ranking.rows ?? [])
const rankingLimit = computed(() => data.value?.ranking.limit ?? 0)
const summary = computed(() => data.value?.summary)
const trendPoints = computed(() => data.value?.daily.points ?? [])

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

// Clear selection on scope change — without this, ranking/summary/daily-trend
// keep filtering by a stale lot_cd that's invisible in the refetched picker,
// silently producing empty / misleading numbers.
watch(
  () => [props.fab, userDateRange.value.start, userDateRange.value.end],
  () => {
    if (selectedLot.value === null && lotSearch.value === '' && selectedCategories.value.length === 0) return
    selectedLot.value = null
    lotSearch.value = ''
    selectedCategories.value = []
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
    tone: 'text-(--sk-ink)'
  },
  {
    label: 'Total executions',
    value: summary.value ? summary.value.total_executions.toLocaleString() : '—',
    tone: 'text-(--sk-ink)'
  },
  {
    label: 'Avg meastime',
    value: summary.value ? formatSecondsAsDuration(Math.round(summary.value.avg_meastime)) : '—',
    tone: 'text-(--sk-ink)'
  }
])

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

const sortableColumnIds = ['meas_counts', 'avg_meastime', 'total_meastime'] as const
type SortableColumnId = typeof sortableColumnIds[number]

const sorting = ref<SortingState>([
  { id: 'total_meastime', desc: true }
])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const sortedRankingRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRankingRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  return [...filteredRankingRows.value].sort((a, b) => (a[id] - b[id]) * dir)
})

const pageCount = computed(
  () => Math.max(1, Math.ceil(sortedRankingRows.value.length / pageSizeNumber.value))
)
const pageStart = computed(
  () => sortedRankingRows.value.length === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1
)
const pageEnd = computed(
  () => Math.min(currentPage.value * pageSizeNumber.value, sortedRankingRows.value.length)
)

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSizeNumber.value
  return sortedRankingRows.value.slice(start, start + pageSizeNumber.value)
})

watch([tableSearch, pageSize, cacheKey, sorting], () => {
  currentPage.value = 1
})

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
  const id = (sorting.value[0]?.id ?? 'total_meastime') as SortableColumnId
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
    grid: { left: 8, right: 24, top: 8, bottom: 24, containLabel: true },
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
      itemStyle: { borderRadius: [0, 4, 4, 0] }
    }]
  }
})

useEchart(barEl, barOption)

const totalForShare = computed(
  () => rankingRows.value.reduce((sum, row) => sum + row.total_meastime, 0)
)

const columns: TableColumn<RecipeTatRow>[] = [
  { accessorKey: 'rank', header: '#', size: 56 },
  { accessorKey: 'full_name', header: 'full name', size: 240 },
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
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const fab = (props.fab || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-${today}.csv`
})

const downloadRankingCsv = () => {
  const headers = [
    'rank', 'full_name', 'class',
    'meas_count', 'avg_meastime_sec', 'total_meastime_sec',
    'last_run', 'share_pct'
  ]
  const total = totalForShare.value
  const rows = sortedRankingRows.value.map(r => [
    r.rank,
    r.full_name,
    r.class_name,
    r.meas_counts,
    r.avg_meastime,
    r.total_meastime,
    r.last_run,
    total ? (r.total_meastime / total * 100).toFixed(2) : '0.00'
  ])
  downloadCsv(exportFileName.value, headers, rows)
}
</script>
