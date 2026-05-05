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
          size="xs"
          color="neutral"
          variant="outline"
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
        class="grid grid-cols-1 gap-3 xl:grid-cols-3"
      >
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
                {{ text.chartParaAllTitle }}
              </p>
              <span class="text-[10.5px] text-zinc-400">para_all</span>
            </div>
          </template>
          <div
            ref="paraAllEl"
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
    </template>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
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
const echartsThemeName = computed(() => colorMode.value === 'dark' ? 'dark' : 'vintage')

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
  chartParaAllTitle: '전체 파라미터 수',
  chartAvailRecipeTitle: '가용 레시피 수',
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

const lotLabels = computed(() => rows.value.map(row => row.lot_cd))

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

const baseDataZoom = [
  { type: 'inside' as const, xAxisIndex: 0, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
  { type: 'slider' as const, xAxisIndex: 0, height: 21, bottom: 6, brushSelect: false }
]

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
  yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
  series: [
    { name: 'para_16', type: 'bar', stack: 'para', data: rows.value.map(r => r.para_16) },
    { name: 'para_13', type: 'bar', stack: 'para', data: rows.value.map(r => r.para_13) },
    { name: 'para_9', type: 'bar', stack: 'para', data: rows.value.map(r => r.para_9) },
    { name: 'para_5', type: 'bar', stack: 'para', data: rows.value.map(r => r.para_5) }
  ]
}))

const paraAllOption = computed<EChartsOption>(() => ({
  tooltip: baseTooltip,
  grid: baseGrid,
  dataZoom: baseDataZoom,
  xAxis: {
    type: 'category',
    data: lotLabels.value,
    axisLabel: { fontSize: 10, interval: 0, rotate: lotLabels.value.length > 8 ? 35 : 0 }
  },
  yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
  series: [{
    name: 'para_all',
    type: 'bar',
    data: rows.value.map(r => r.para_all)
  }]
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
  yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
  series: [{
    name: 'avail_recipe',
    type: 'bar',
    data: rows.value.map(r => r.avail_recipe)
  }]
}))

const stackedEl = ref<HTMLDivElement | null>(null)
const paraAllEl = ref<HTMLDivElement | null>(null)
const availRecipeEl = ref<HTMLDivElement | null>(null)

const useEchart = (
  elRef: Ref<HTMLDivElement | null>,
  optionRef: ComputedRef<EChartsOption>
) => {
  let chart: ECharts | null = null
  let resizeHandler: (() => void) | null = null

  const ensureChart = () => {
    if (chart || !elRef.value) return
    chart = echarts.init(elRef.value, echartsThemeName.value)
    chart.setOption(optionRef.value)
    if (!resizeHandler) {
      resizeHandler = () => chart?.resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  onMounted(() => {
    ensureChart()
  })

  // The chart container only renders once data is ready (v-else block), so
  // re-run ensureChart whenever the element ref appears.
  watch(elRef, (next) => {
    if (next) ensureChart()
  })

  watch(optionRef, (next) => {
    chart?.setOption(next, true)
  })

  // ECharts binds a theme at init time; swapping themes requires dispose +
  // re-init on the same DOM node.
  watch(echartsThemeName, () => {
    if (!elRef.value) return
    chart?.dispose()
    chart = echarts.init(elRef.value, echartsThemeName.value)
    chart.setOption(optionRef.value)
  })

  onBeforeUnmount(() => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    chart?.dispose()
    chart = null
  })
}

useEchart(stackedEl, stackedOption)
useEchart(paraAllEl, paraAllOption)
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
