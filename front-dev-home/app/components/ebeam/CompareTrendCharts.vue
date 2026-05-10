<template>
  <div class="space-y-3">
    <div class="dashboard-surface rounded-2xl px-3.5 py-2.5">
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-mono text-[10px] text-zinc-400">{{ text.rangeLabel }}</span>
        <USelect
          v-model="startDate"
          size="xs"
          :items="dateItems"
          class="min-w-[7.5rem]"
        />
        <span class="text-[12px] text-zinc-400">~</span>
        <USelect
          v-model="endDate"
          size="xs"
          :items="dateItems"
          class="min-w-[7.5rem]"
        />
      </div>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <span class="font-mono text-[10px] text-zinc-400">{{ text.filterLabel }}</span>
        <div
          role="radiogroup"
          aria-label="Display filter"
          class="flex flex-wrap items-center gap-1"
        >
          <button
            v-for="option in filterOptions"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="displayFilter === option.value"
            class="inline-flex h-7 items-center gap-1 rounded-md px-3 text-[12px] font-medium ring-1 transition-colors"
            :class="displayFilter === option.value
              ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
              : 'bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
            @click="displayFilter = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <span
          v-if="visibleLots.length > 0 && visibleLots.length !== lotCds.length"
          class="ml-1 font-mono text-[10px] text-zinc-500"
        >
          {{ visibleLots.length }} / {{ lotCds.length }}
        </span>
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
      v-else-if="trendError"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      {{ text.loadError }}
    </div>
    <div
      v-else-if="dates.length === 0 || visibleLots.length === 0"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-zinc-500"
    >
      {{ text.noRows }}
    </div>
    <div
      v-else
      class="grid grid-cols-1 gap-3 xl:grid-cols-2"
    >
      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              {{ text.chartParaTitle }}
            </p>
            <span class="text-[10.5px] text-zinc-400">para_all</span>
          </div>
        </template>
        <div
          ref="paraEl"
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
              {{ text.chartRecipeTitle }}
            </p>
            <span class="text-[10.5px] text-zinc-400">avail_recipe</span>
          </div>
        </template>
        <div
          ref="recipeEl"
          class="h-72 w-full"
        />
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { SummaryBucketKey, SummaryRow } from '~/composables/useRecipeStatisticsApi'

const props = defineProps<{
  lotCds: string[]
  bucket: SummaryBucketKey
}>()

type DisplayFilter = 'all' | 'topPara' | 'topRecipe' | 'topDelta'

const text = {
  rangeLabel: '기간',
  filterLabel: '표시',
  chartParaTitle: '파라미터 추이',
  chartRecipeTitle: '운용 레시피수 추이',
  loading: '추이 데이터 불러오는 중',
  loadError: '추이 데이터를 불러오지 못했습니다.',
  noRows: '표시할 추이 데이터가 없습니다.'
} as const

const filterOptions: { label: string, value: DisplayFilter }[] = [
  { label: '전체', value: 'all' },
  { label: '파라미터 상위 20%', value: 'topPara' },
  { label: '운용 레시피 상위 20%', value: 'topRecipe' },
  { label: '변화율 상위 20%', value: 'topDelta' }
]

const displayFilter = ref<DisplayFilter>('all')
const startDate = ref<string>('')
const endDate = ref<string>('')

const { fetchRecipeTrend } = useRecipeStatisticsApi()

const lotsKey = computed(() => [...props.lotCds].sort().join(','))

const { data, pending, error: trendError } = await useAsyncData(
  'recipe-trend',
  () => {
    if (props.lotCds.length === 0) {
      return Promise.resolve({ dates: [], trend: {} })
    }
    return fetchRecipeTrend(props.lotCds)
  },
  { watch: [lotsKey] }
)

// First successful response defines the available date window. Subsequent
// fetches just refresh values; we do NOT re-pass start/end to the server
// (slicing happens client-side from the cached full window for snappier
// filter changes — payload is small, ~8 dates × tens of devices).
const allDates = computed(() => data.value?.dates ?? [])

watch(allDates, (next) => {
  if (next.length === 0) {
    startDate.value = ''
    endDate.value = ''
    return
  }
  if (!startDate.value || !next.includes(startDate.value)) {
    startDate.value = next[0]!
  }
  if (!endDate.value || !next.includes(endDate.value)) {
    endDate.value = next[next.length - 1]!
  }
}, { immediate: true })

const dateItems = computed(() => allDates.value.map(d => ({ label: d, value: d })))

const dates = computed(() => {
  if (!startDate.value || !endDate.value) return allDates.value
  const lo = startDate.value <= endDate.value ? startDate.value : endDate.value
  const hi = startDate.value <= endDate.value ? endDate.value : startDate.value
  return allDates.value.filter(d => d >= lo && d <= hi)
})

const summaryAt = (date: string): SummaryRow[] => {
  const bucketPayload = data.value?.trend?.[date]
  if (!bucketPayload) return []
  const list = (bucketPayload as Record<string, unknown>)[props.bucket]
  return Array.isArray(list) ? list as SummaryRow[] : []
}

// Quick lookup: lot -> SummaryRow at a given date.
const summaryByLotAt = (date: string): Record<string, SummaryRow> => {
  const out: Record<string, SummaryRow> = {}
  for (const row of summaryAt(date)) {
    out[row.lot_cd] = row
  }
  return out
}

const visibleLots = computed<string[]>(() => {
  const allLots = props.lotCds
  if (allLots.length === 0 || dates.value.length === 0) return []
  // Filter is meaningful only when there are enough devices to subset.
  if (displayFilter.value === 'all' || allLots.length <= 5) return allLots

  const n = Math.max(1, Math.ceil(allLots.length * 0.2))
  const lastIdx = dates.value.length - 1
  const last = summaryByLotAt(dates.value[lastIdx]!)
  const first = summaryByLotAt(dates.value[0]!)

  const score = (lot: string): number => {
    const lastRow = last[lot]
    const firstRow = first[lot]
    if (!lastRow || !firstRow) return -Infinity
    if (displayFilter.value === 'topPara') return lastRow.para_all
    if (displayFilter.value === 'topRecipe') return lastRow.avail_recipe
    // topDelta: absolute change rate on para_all.
    return firstRow.para_all > 0
      ? Math.abs((lastRow.para_all - firstRow.para_all) / firstRow.para_all)
      : 0
  }

  return [...allLots].sort((a, b) => score(b) - score(a)).slice(0, n)
})

// Precompute aligned series data (avoids per-render .find()).
const seriesByLot = computed(() => {
  const dateMaps = dates.value.map(d => summaryByLotAt(d))
  const out = new Map<string, { para: (number | null)[], recipe: (number | null)[] }>()
  for (const lot of visibleLots.value) {
    const para: (number | null)[] = []
    const recipe: (number | null)[] = []
    for (const map of dateMaps) {
      const row = map[lot]
      para.push(row ? row.para_all : null)
      recipe.push(row ? row.avail_recipe : null)
    }
    out.set(lot, { para, recipe })
  }
  return out
})

const baseTooltip = {
  trigger: 'axis' as const
}

const baseGrid = { left: 48, right: 16, top: 36, bottom: 28, containLabel: true }

const baseYAxis = {
  type: 'value' as const,
  axisLabel: { fontSize: 10 },
  splitLine: { show: false }
}

const buildLineOption = (
  pick: (entry: { para: (number | null)[], recipe: (number | null)[] }) => (number | null)[]
): EChartsOption => ({
  tooltip: baseTooltip,
  legend: { type: 'scroll', top: 0, right: 8, textStyle: { fontSize: 11 } },
  grid: baseGrid,
  xAxis: {
    type: 'category',
    data: dates.value,
    axisLabel: { fontSize: 10 }
  },
  yAxis: baseYAxis,
  // Helps when `visibleLots` runs into the dozens; ECharts batches the
  // draw and the user sees a brief "drawing in" motion.
  progressive: 400,
  progressiveThreshold: 1500,
  series: visibleLots.value.map(lot => ({
    name: lot,
    type: 'line',
    smooth: true,
    showSymbol: false,
    emphasis: { focus: 'series' as const },
    data: pick(seriesByLot.value.get(lot)!)
  }))
})

const paraOption = computed<EChartsOption>(() => buildLineOption(e => e.para))
const recipeOption = computed<EChartsOption>(() => buildLineOption(e => e.recipe))

const paraEl = ref<HTMLDivElement | null>(null)
const recipeEl = ref<HTMLDivElement | null>(null)

useEchart(paraEl, paraOption)
useEchart(recipeEl, recipeOption)
</script>
