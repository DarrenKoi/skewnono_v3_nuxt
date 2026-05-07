<template>
  <div class="space-y-3">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <div class="min-w-0">
          <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            CD-SEM
          </p>
          <h1 class="text-2xl font-bold whitespace-nowrap text-zinc-950 dark:text-zinc-50">
            {{ text.title }}
          </h1>
        </div>
        <div class="hidden h-9 w-px self-end mb-1 bg-zinc-200 dark:bg-zinc-700 md:block" />
        <span class="self-end mb-2 text-xs text-zinc-500">
          {{ selectedLotsLabel }}
        </span>
      </div>

      <div class="flex items-center gap-2 self-start md:self-auto">
        <span
          v-if="data?.date"
          class="rounded-md bg-zinc-100 px-2 py-1 font-mono text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
        >
          {{ text.latestDate }} {{ data.date }}
        </span>
        <UButton
          size="md"
          color="neutral"
          variant="subtle"
          icon="i-lucide-arrow-left"
          :label="text.back"
          @click="goBack"
        />
      </div>
    </div>

    <div
      v-if="selectedLots.length === 0"
      class="dashboard-surface flex flex-col items-center justify-center rounded-2xl px-6 py-16 text-center"
    >
      <div class="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-50 text-zinc-400 ring-1 ring-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800">
        <UIcon
          name="i-lucide-inbox"
          class="h-5 w-5"
        />
      </div>
      <p class="text-sm font-medium text-zinc-700 dark:text-zinc-200">
        {{ text.emptyTitle }}
      </p>
      <p class="mt-1 text-xs text-zinc-500">
        {{ text.emptyDesc }}
      </p>
      <UButton
        class="mt-4"
        size="sm"
        :label="text.emptyCta"
        trailing-icon="i-lucide-arrow-right"
        @click="goBack"
      />
    </div>

    <template v-else>
      <div class="dashboard-surface rounded-2xl px-3.5 py-2.5">
        <div class="flex flex-wrap items-center gap-2">
          <div class="flex items-center gap-1.5">
            <span class="font-mono text-[10px] text-zinc-400">bucket</span>
            <UPopover>
              <UButton
                type="button"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-info"
                aria-label="Bucket 설명"
                class="h-6 w-6 rounded-full p-0 text-zinc-500"
              />
              <template #content>
                <div class="w-72 space-y-3 p-3">
                  <div>
                    <p class="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                      {{ text.bucketHelpTitle }}
                    </p>
                    <p class="mt-1 text-xs leading-5 text-zinc-500 dark:text-zinc-400">
                      {{ text.bucketHelpIntro }}
                    </p>
                  </div>
                  <dl class="space-y-2">
                    <div
                      v-for="option in bucketOptions"
                      :key="`${option.value}-help`"
                      class="rounded-md bg-zinc-50 px-2.5 py-2 dark:bg-zinc-900"
                    >
                      <dt class="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                        {{ option.label }}
                      </dt>
                      <dd class="mt-1 text-xs leading-5 text-zinc-600 dark:text-zinc-400">
                        {{ option.description }}
                      </dd>
                    </div>
                  </dl>
                </div>
              </template>
            </UPopover>
          </div>
          <div
            role="radiogroup"
            aria-label="Summary bucket"
            class="flex flex-wrap items-center gap-1"
          >
            <button
              v-for="option in bucketOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedBucket === option.value"
              class="inline-flex h-7 items-center gap-1 rounded-md px-3 text-[12px] font-medium ring-1 transition-colors"
              :class="selectedBucket === option.value
                ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="selectedBucket = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <span class="font-mono text-[10px] text-zinc-400">sort</span>
          <div
            role="radiogroup"
            aria-label="Sort by metric"
            class="flex flex-wrap items-center gap-1"
          >
            <button
              v-for="option in sortOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedSort === option.value"
              class="inline-flex h-7 items-center gap-1 rounded-md px-3 text-[12px] font-medium ring-1 transition-colors"
              :class="selectedSort === option.value
                ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
                : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="selectedSort = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="pending"
        class="dashboard-surface flex items-center justify-center gap-2 rounded-2xl px-4 py-12 text-sm text-zinc-500"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        {{ text.loading }}
      </div>
      <div
        v-else-if="error"
        class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <div
        v-else-if="rows.length === 0"
        class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-zinc-500"
      >
        {{ text.noRows }}
      </div>
      <div
        v-else
        class="space-y-3"
      >
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <UCard
            class="dashboard-surface rounded-2xl"
            :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
          >
            <template #header>
              <div class="flex items-center justify-between gap-3">
                <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
                  {{ text.chartStackedTitle }}
                </p>
                <span class="text-[10.5px] text-zinc-400">para_16 / 13 / 9 / 5</span>
              </div>
            </template>
            <div
              ref="stackedEl"
              class="h-72 w-full"
            />
          </UCard>

          <UCard
            class="dashboard-surface rounded-2xl"
            :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
          >
            <template #header>
              <div class="flex items-center justify-between gap-3">
                <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
                  {{ text.chartAvailRecipeTitle }}
                </p>
                <span class="text-[10.5px] text-zinc-400">avail_recipe</span>
              </div>
            </template>
            <div
              ref="availRecipeEl"
              class="h-72 w-full"
            />
          </UCard>
        </div>

        <div class="flex items-center gap-2 px-1 pt-2 text-[11px] uppercase tracking-wide text-zinc-400">
          <span class="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
          <span>{{ text.trendSection }}</span>
          <span class="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
        </div>

        <EbeamCompareTrendCharts
          :lot-cds="selectedLots"
          :bucket="selectedBucket"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import type { SummaryBucketKey, SummaryRow } from '~/composables/useRecipeStatisticsApi'
import { registerEchartsThemes } from '~/utils/echartsThemes'

registerEchartsThemes(echarts)

definePageMeta({
  hideFabSidebar: true
})

const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fetchRecipeStatistics } = useRecipeStatisticsApi()
const colorMode = useColorMode()

const { selectedDeviceLots: selectedLots } = useDeviceCart()

const text = {
  title: '디바이스 비교',
  back: '돌아가기',
  latestDate: '최신 데이터',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  noRows: '조건에 맞는 요약 데이터가 없습니다.',
  emptyTitle: '선택된 디바이스가 없습니다',
  emptyDesc: '디바이스 통계 페이지에서 2개 이상을 선택해 주세요.',
  emptyCta: '디바이스 선택으로',
  chartStackedTitle: '파라미터 분포 (스택)',
  chartAvailRecipeTitle: '운용 레시피수',
  trendSection: '주간 추이',
  selected: '선택',
  bucketHelpTitle: 'Bucket 의미',
  bucketHelpIntro: 'MMDM recipe step을 어떤 기준으로 모아 볼지 선택합니다.'
} as const

type BucketOption = { label: string, value: SummaryBucketKey, description: string }

const bucketOptions: BucketOption[] = [
  {
    label: 'All',
    value: 'all_summary',
    description: 'MMDM system의 모든 Step을 표시합니다. Full job과 Sample job을 함께 포함합니다.'
  },
  {
    label: 'Only Normal',
    value: 'only_normal_summary',
    description: '정규 Recipe만 표시합니다. 스텝명에 CD만 포함된 Step 기준입니다.'
  },
  {
    label: 'Mother Normal',
    value: 'mother_normal_summary',
    description: '정규 Recipe 중 TAT에 영향을 주는 파라미터만 선별합니다.'
  },
  {
    label: 'Only Sample',
    value: 'only_sample_summary',
    description: 'Sample Recipe만 표시합니다. _S, SE Step을 선별합니다.'
  }
]

const selectedBucket = ref<SummaryBucketKey>('all_summary')

type SortKey = 'default' | 'paraStack' | 'availRecipe'

const sortOptions = [
  { label: '이름순', value: 'default' },
  { label: '파라미터', value: 'paraStack' },
  { label: '운용 레시피수', value: 'availRecipe' }
] as const

const selectedSort = ref<SortKey>('default')

const sortMetric: Record<Exclude<SortKey, 'default'>, (r: SummaryRow) => number> = {
  paraStack: r => r.para_16 + r.para_13 + r.para_9 + r.para_5,
  availRecipe: r => r.avail_recipe
}

const { data, pending, error } = await useAsyncData(
  'recipe-statistics',
  () => {
    if (selectedLots.value.length === 0) {
      return Promise.resolve({ date: null, buckets: {} })
    }
    return fetchRecipeStatistics(selectedLots.value)
  },
  { watch: [selectedLots] }
)

const rows = computed<SummaryRow[]>(() => {
  const buckets = data.value?.buckets
  if (!buckets) return []
  const list = (buckets as Record<string, unknown>)[selectedBucket.value]
  return Array.isArray(list) ? (list as SummaryRow[]) : []
})

const sortedRows = computed<SummaryRow[]>(() => {
  if (selectedSort.value === 'default') {
    return [...rows.value].sort((a, b) => a.lot_cd.localeCompare(b.lot_cd))
  }
  const get = sortMetric[selectedSort.value]
  return [...rows.value].sort((a, b) => get(b) - get(a))
})

const lotLabels = computed(() => sortedRows.value.map(row => row.lot_cd))

const mean = (xs: number[]) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0
// Sample stdev (n-1): we treat the selected devices as a sample, not the whole population.
const stdDev = (xs: number[]) => {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1))
}

const stackTotals = computed(() => sortedRows.value.map(r => r.para_16 + r.para_13 + r.para_9 + r.para_5))
const availRecipeValues = computed(() => sortedRows.value.map(r => r.avail_recipe))

const avgStackTotal = computed(() => mean(stackTotals.value))
const avgAvailRecipe = computed(() => mean(availRecipeValues.value))

const stdStackTotal = computed(() => stdDev(stackTotals.value))
const stdAvailRecipe = computed(() => stdDev(availRecipeValues.value))

const selectedLotsLabel = computed(() => {
  if (selectedLots.value.length === 0) return ''
  const preview = selectedLots.value.slice(0, 4).join(', ')
  const overflow = selectedLots.value.length - 4
  return overflow > 0
    ? `${text.selected}: ${preview} 외 ${overflow}개`
    : `${text.selected}: ${preview}`
})

const baseTooltip = {
  trigger: 'axis' as const,
  axisPointer: { type: 'shadow' as const }
}

const baseGrid = { left: 48, right: 16, top: 36, bottom: 55, containLabel: true }

const baseYAxis = {
  type: 'value' as const,
  axisLabel: { fontSize: 10 },
  splitLine: { show: false }
}

const baseDataZoom = [
  { type: 'inside' as const, xAxisIndex: 0, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
  { type: 'slider' as const, xAxisIndex: 0, height: 21, bottom: 6, brushSelect: false }
]

const markLineColor = computed(() => colorMode.value === 'dark' ? '#e4e4e7' : '#27272a')

const sigmaLineStyle = computed(() => ({
  type: 'dotted' as const,
  color: markLineColor.value,
  width: 1,
  opacity: 0.55
}))

const buildStatsMarkLine = (avg: number, sd: number) => ({
  symbol: 'none' as const,
  silent: true,
  lineStyle: { type: 'dashed' as const, color: markLineColor.value, width: 1.5 },
  label: {
    fontSize: 10,
    color: markLineColor.value,
    backgroundColor: 'transparent'
  },
  data: [
    {
      yAxis: avg,
      label: { position: 'insideEndTop' as const, formatter: `평균 ${Math.round(avg)}` }
    },
    ...(sd > 0
      ? [
          {
            yAxis: avg + sd,
            lineStyle: sigmaLineStyle.value,
            label: { position: 'insideEndTop' as const, formatter: `+1σ ${Math.round(avg + sd)}` }
          },
          {
            yAxis: avg - sd,
            lineStyle: sigmaLineStyle.value,
            label: { position: 'insideEndBottom' as const, formatter: `-1σ ${Math.round(avg - sd)}` }
          }
        ]
      : [])
  ]
})

const stackedOption = computed<EChartsOption>(() => ({
  tooltip: baseTooltip,
  legend: { top: 0, right: 0, textStyle: { fontSize: 11 } },
  grid: baseGrid,
  dataZoom: baseDataZoom,
  xAxis: {
    type: 'category',
    data: lotLabels.value,
    axisLabel: { fontSize: 10, interval: 0, rotate: lotLabels.value.length > 8 ? 35 : 0 }
  },
  yAxis: baseYAxis,
  series: [
    { name: 'para_16', type: 'bar', stack: 'para', data: sortedRows.value.map(r => r.para_16) },
    { name: 'para_13', type: 'bar', stack: 'para', data: sortedRows.value.map(r => r.para_13) },
    { name: 'para_9', type: 'bar', stack: 'para', data: sortedRows.value.map(r => r.para_9) },
    {
      name: 'para_5',
      type: 'bar',
      stack: 'para',
      data: sortedRows.value.map(r => r.para_5),
      markLine: buildStatsMarkLine(avgStackTotal.value, stdStackTotal.value)
    }
  ]
}))

const availRecipeOption = computed<EChartsOption>(() => ({
  tooltip: baseTooltip,
  grid: baseGrid,
  dataZoom: baseDataZoom,
  xAxis: {
    type: 'category',
    data: lotLabels.value,
    axisLabel: { fontSize: 10, interval: 0, rotate: lotLabels.value.length > 8 ? 35 : 0 }
  },
  yAxis: baseYAxis,
  series: [{
    name: 'avail_recipe',
    type: 'bar',
    data: sortedRows.value.map(r => r.avail_recipe),
    markLine: buildStatsMarkLine(avgAvailRecipe.value, stdAvailRecipe.value)
  }]
}))

const stackedEl = ref<HTMLDivElement | null>(null)
const availRecipeEl = ref<HTMLDivElement | null>(null)

useEchart(stackedEl, stackedOption)
useEchart(availRecipeEl, availRecipeOption)

const goBack = async () => {
  await navigateTo(`/ebeam/cd-sem/${route.params.fab}/device-statistics`)
}

onMounted(() => {
  setToolType('cd-sem')
  const fabParam = String(route.params.fab ?? '').toUpperCase()
  if (fabParam) setFab(fabParam)
})
</script>
