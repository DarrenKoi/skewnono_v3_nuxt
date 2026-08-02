<template>
  <div class="space-y-3">
    <EbeamMetaBar
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
      :stats="metaStats"
      :as-of="data?.date ?? ''"
    >
      <template #leading>
        <AppBackButton
          :label="text.back"
          @click="goBack"
        />
      </template>
    </EbeamMetaBar>

    <div
      v-if="selectedLots.length === 0"
      class="dashboard-surface flex flex-col items-center justify-center rounded-2xl px-6 py-16 text-center"
    >
      <div class="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-50 text-(--sk-ink-muted) ring-1 ring-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800">
        <UIcon
          name="i-lucide-inbox"
          class="h-5 w-5"
        />
      </div>
      <p class="text-sm font-medium text-zinc-700 dark:text-zinc-200">
        {{ text.emptyTitle }}
      </p>
      <p class="mt-1 sk-meta">
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
        <div class="space-y-1.5">
          <span class="font-mono text-[10px] text-(--sk-ink-muted)">bucket</span>
          <div
            role="radiogroup"
            aria-label="Summary bucket"
            class="grid grid-cols-1 gap-1.5 sm:grid-cols-2 xl:grid-cols-4"
          >
            <button
              v-for="option in bucketOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedBucket === option.value"
              class="rounded-lg px-3 py-2 text-left ring-1 transition-colors"
              :class="selectedBucket === option.value
                ? 'bg-(--sk-accent-tint) ring-(--sk-accent)'
                : 'bg-white ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:ring-zinc-700 dark:hover:bg-zinc-800'"
              @click="selectedBucket = option.value"
            >
              <span
                class="flex items-center gap-1.5 text-[12px] font-semibold"
                :class="selectedBucket === option.value ? 'text-(--sk-accent)' : 'text-(--sk-ink)'"
              >
                {{ option.label }}
                <UIcon
                  v-if="selectedBucket === option.value"
                  name="i-lucide-check"
                  class="h-3.5 w-3.5"
                />
              </span>
              <span class="mt-0.5 block text-[11px] leading-4 text-(--sk-ink-muted)">{{ option.description }}</span>
            </button>
          </div>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <span class="font-mono text-[10px] text-(--sk-ink-muted)">sort</span>
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
              :class="chipClass(selectedSort === option.value)"
              @click="selectedSort = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>

      <AppLoadingState
        v-if="pending"
        variant="inline"
        class="dashboard-surface rounded-2xl"
        :title="text.loading"
      />
      <div
        v-else-if="error"
        class="dashboard-surface rounded-2xl px-4 py-12 text-center sk-body text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <div
        v-else-if="rows.length === 0"
        class="dashboard-surface rounded-2xl px-4 py-12 text-center sk-body"
      >
        {{ text.noRows }}
      </div>
      <div
        v-else
        class="space-y-6"
      >
        <section class="space-y-3">
          <header class="comparison-section-head">
            <span
              class="comparison-section-head__bar"
              aria-hidden="true"
            />
            <div>
              <h2 class="comparison-section-head__title">
                {{ text.chartsGroupTitle }}
              </h2>
              <p class="comparison-section-head__subtitle">
                {{ text.chartsGroupSubtitle }}
              </p>
            </div>
          </header>

          <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <UCard
              class="dashboard-surface rounded-2xl"
              :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
            >
              <template #header>
                <div class="flex items-center justify-between gap-3">
                  <p class="sk-title">
                    {{ text.chartStackedTitle }}
                  </p>
                  <span class="text-[11px] text-(--sk-ink-muted)">para_16 / 13 / 9 / 5</span>
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
                  <p class="sk-title">
                    {{ text.chartAvailRecipeTitle }}
                  </p>
                  <span class="text-[11px] text-(--sk-ink-muted)">avail_recipe</span>
                </div>
              </template>
              <div
                ref="availRecipeEl"
                class="h-72 w-full"
              />
            </UCard>
          </div>
        </section>

        <CdsemComparisonLotTable
          :rows="profiledRows"
          @select-lot="openLotDetail"
          @open-outliers="openOutlierDrill"
        />
        <CdsemComparisonLotDetailModal
          v-model:open="lotModalOpen"
          :row="selectedLotRow"
          :bucket="selectedBucket"
          :recipe-rows="recipeRowsForBucket"
          :trend="trend ?? null"
        />
        <EbeamDevstatDrillSlideover
          v-model:open="drillOpen"
          :device="activeDrill"
          highlight-label="초과"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TopLevelFormatterParams } from 'echarts/types/dist/shared'
import { summaryToRecipeInfoBucket, type RecipeInfoRow, type SummaryBucketKey, type SummaryRow } from '~/composables/useRecipeStatisticsApi'
import {
  augmentRow, buildLotVerdicts, paraTotal, recipeKey,
  type HealthAugmentedRow, type RuleSet
} from '~/utils/lotHealth'
import type { RecipeInput } from '~/utils/ruleEngine'
import { buildDeviceOutliers, groupRecipesByLot, attachProfile, type Profiled } from '~/utils/deviceProfile'
import { toOutlierDrill, type DrillDevice } from '~/utils/deviceDrill'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { paraColors, paraColorsDark, paraOrder } from '~/components/cdsem/comparison/healthTokens'

definePageMeta({
  hideFabSidebar: true
})

const { setToolType } = useNavigation()
const { fetchRecipeStatistics, fetchRecipeTrend } = useRecipeStatisticsApi()
const { fetchRecipeParams } = useDeviceStatisticsApi()
const { fetchRulesForFabs } = useMeasurementRulesApi()
const colorMode = useColorMode()

const { selectedDeviceLots: selectedLots } = useDeviceCart()

const text = {
  title: '디바이스 분석',
  subtitle: '선택한 Lot의 recipe 파라미터 분포와 운용 레시피수를 확인합니다.',
  back: '돌아가기',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  noRows: '조건에 맞는 요약 데이터가 없습니다.',
  emptyTitle: '선택된 디바이스가 없습니다',
  emptyDesc: '디바이스 통계 페이지에서 1개 이상 선택해 주세요.',
  emptyCta: '디바이스 선택으로',
  chartsGroupTitle: '파라미터 비교',
  chartsGroupSubtitle: '선택한 Lot 전체의 분포를 한눈에 봅니다.',
  chartStackedTitle: '파라미터 분포 (스택)',
  chartAvailRecipeTitle: '운용 레시피수'
} as const

const metaStats = computed<MetaBarStat[]>(() =>
  selectedLots.value.length > 0
    ? [{ key: 'selected', value: selectedLots.value.length, label: '선택 디바이스', tone: 'accent' }]
    : []
)

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
  paraStack: paraTotal,
  availRecipe: r => r.avail_recipe
}

const [
  { data, pending, error },
  { data: trend },
  { data: recipeParams }
] = await Promise.all([
  useAsyncData(
    'recipe-statistics',
    () => {
      if (selectedLots.value.length === 0) {
        return Promise.resolve({ date: null, buckets: {} })
      }
      return fetchRecipeStatistics(selectedLots.value)
    },
    { watch: [selectedLots] }
  ),
  useAsyncData(
    'recipe-trend-comparison',
    () => {
      if (selectedLots.value.length === 0) {
        return Promise.resolve({ dates: [], trend: {} })
      }
      return fetchRecipeTrend(selectedLots.value)
    },
    { watch: [selectedLots] }
  ),
  // health 판정용 원본. selectedLots 에만 의존하므로 위 둘과 같은 단계에서 나갑니다
  // — 뒤에 세우면 페이지에서 가장 무거운 응답(lot 당 약 124 KB)이 직렬 구간에
  // 들어갑니다. 빈 목록 가드는 fetchRecipeParams 안에 있습니다(전 lot = 약 522 MB).
  useAsyncData<RecipeInput[]>(
    'recipe-params-comparison',
    () => fetchRecipeParams(selectedLots.value),
    { watch: [selectedLots] }
  )
])

const rows = computed<SummaryRow[]>(() => {
  const buckets = data.value?.buckets
  if (!buckets) return []
  const list = (buckets as Record<string, unknown>)[selectedBucket.value]
  return Array.isArray(list) ? (list as SummaryRow[]) : []
})

const recipeRowsForBucket = computed<RecipeInfoRow[]>(() => {
  const buckets = data.value?.buckets
  if (!buckets) return []
  const list = (buckets as Record<string, unknown>)[summaryToRecipeInfoBucket[selectedBucket.value]]
  return Array.isArray(list) ? (list as RecipeInfoRow[]) : []
})

// 룰은 fab 단위입니다. 선택에 들어 있는 fab 만 받아오고, 룰이 없는 fab(M 계열 —
// D22 로 폐기)은 null 이 되어 "판정 없음" 으로 표시됩니다.
//
// watch 대상이 문자열인 것이 중요합니다. computed 가 배열을 돌려주면 매번 새
// identity 라 useAsyncData 의 Object.is 비교가 항상 달라지고, bucket 을 누를
// 때마다 fab 6개 룰을 전부 다시 받습니다 (/api 는 20 req / 5 s 제한).
const selectedFabKey = computed(() =>
  [...new Set(rows.value.map(r => r.fac_id))].sort().join(',')
)

const { data: rulesByFab } = await useAsyncData<Record<string, RuleSet | null>>(
  'measurement-rules-by-fab',
  async () => {
    const facIds = selectedFabKey.value ? selectedFabKey.value.split(',') : []
    if (facIds.length === 0) return {}
    const versions = await fetchRulesForFabs(facIds)
    return Object.fromEntries(
      Object.entries(versions).map(([facId, version]) => [
        facId,
        version ? { cells: version.cells, thresholds: version.thresholds } : null
      ])
    )
  },
  { watch: [selectedFabKey] }
)

// 요약 행은 **버킷 단위**인데 recipe-params 는 버킷 축이 없습니다. 버킷의
// recipe_id 로 좁히지 않으면 버킷을 바꿔도 health 만 그대로인 모순이 생깁니다.
// recipe_id 로 좁힐 수 있는 것은 그것이 표면을 가로지르는 조인 키이기 때문입니다.
const bucketRecipeKeys = computed(() => {
  const keys = new Set<string>()
  for (const row of recipeRowsForBucket.value) keys.add(recipeKey(row.lot_cd, row.recipe_id))
  return keys
})

const lotVerdicts = computed(() =>
  buildLotVerdicts(recipeParams.value ?? [], rulesByFab.value ?? {}, bucketRecipeKeys.value)
)

const augmentedRows = computed<HealthAugmentedRow[]>(() =>
  rows.value.map(row => augmentRow(row, lotVerdicts.value.get(row.lot_cd)))
)

// 측정 프로파일(과다 측정 탐지). 별도 페이지였다가 이 표에 합쳤습니다 — 같은
// grain(디바이스 1행)이라 페이지를 나누면 나머지 열이 전부 중복이었습니다.
// 이미 받아 둔 recipeParams 를 재사용하므로 추가 요청은 없습니다.
//
// 묶기는 한 번만 합니다. drill 이 필요로 하는 것도 여기서 만든 바로 그
// RecipeInput[] 이라, 클릭할 때마다 전체 payload(lot 당 약 124 KB)를 다시
// 훑지 않게 map 을 그대로 들고 갑니다.
const recipesByLot = computed(() => groupRecipesByLot(recipeParams.value ?? []))

const deviceOutliers = computed(() => buildDeviceOutliers(recipesByLot.value))

const profiledRows = computed<Profiled<HealthAugmentedRow>[]>(() =>
  augmentedRows.value.map(row => attachProfile(row, deviceOutliers.value.get(row.lot_cd)))
)

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

const ctnDescByLot = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const row of sortedRows.value) map[row.lot_cd] = row.ctn_desc
  return map
})

const escapeHtml = (s: string) => s.replace(/[&<>"']/g, c => (
  c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : '&#39;'
))

const formatBarTooltip = (raw: TopLevelFormatterParams) => {
  const arr = Array.isArray(raw) ? raw : [raw]
  if (arr.length === 0) return ''
  const lot = (arr[0]?.name as string | undefined) ?? ''
  const desc = ctnDescByLot.value[lot] ?? ''
  const header = `<div style="font-weight:600">${escapeHtml(lot)}</div>`
    + (desc ? `<div style="font-size:10px;color:#888;margin:2px 0 6px">${escapeHtml(desc)}</div>` : '')
  const lines = arr.map((p) => {
    // ECharts marker can be a rich-text token object when textStyle.rich is
    // configured; we don't use rich text, so the runtime value is always
    // the HTML <span> string.
    const marker = typeof p.marker === 'string' ? p.marker : ''
    const seriesName = typeof p.seriesName === 'string' ? p.seriesName : ''
    return `<div style="display:flex;justify-content:space-between;gap:16px">`
      + `<span>${marker}${escapeHtml(seriesName)}</span>`
      + `<span style="font-variant-numeric:tabular-nums">${escapeHtml(String(p.value ?? ''))}</span>`
      + `</div>`
  }).join('')
  return header + lines
}

const baseTooltip = {
  trigger: 'axis' as const,
  axisPointer: { type: 'shadow' as const },
  formatter: formatBarTooltip
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

// Deliberately keyed to colorMode, NOT to the chart theme. These lines are
// drawn onto a transparent canvas over the app's card, so what they must
// contrast with is the CARD -- and the theme picker is independent of color
// mode, so a light theme (matlab, vintage, ...) can be active in dark mode.
// Sourcing this from the theme's ink renders #262626 on a dark card.
const markLineColor = computed(() => colorMode.value === 'dark' ? '#e4e4e7' : '#27272a')

// Same para palette as the table's StackedBar cells (dark-aware), so the
// stacked chart, table, and detail modal all read as one color system.
const paraPalette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

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
  series: paraOrder.map((key, index) => ({
    name: key,
    type: 'bar' as const,
    stack: 'para',
    itemStyle: { color: paraPalette.value[key] },
    data: sortedRows.value.map(r => r[key]),
    ...(index === paraOrder.length - 1
      ? { markLine: buildStatsMarkLine(avgStackTotal.value, stdStackTotal.value) }
      : {})
  }))
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
    // No itemStyle.color: sole series, so ECharts already assigns palette[0].
    data: sortedRows.value.map(r => r.avail_recipe),
    markLine: buildStatsMarkLine(avgAvailRecipe.value, stdAvailRecipe.value)
  }]
}))

const stackedEl = ref<HTMLDivElement | null>(null)
const availRecipeEl = ref<HTMLDivElement | null>(null)

useEchart(stackedEl, stackedOption)
useEchart(availRecipeEl, availRecipeOption)

const lotModalOpen = ref(false)
const selectedLotRow = ref<HealthAugmentedRow | null>(null)

const openLotDetail = (row: HealthAugmentedRow) => {
  selectedLotRow.value = row
  lotModalOpen.value = true
}

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openOutlierDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const result = deviceOutliers.value.get(lot_cd)
  if (!result) return
  activeDrill.value = toOutlierDrill(lot_cd, recipes[0]?.ctn_desc ?? '', recipes, result)
  drillOpen.value = true
}

// Caps (and therefore health/violations) are bucket-dependent, so an open
// modal would show stale numbers after a bucket switch — close it instead.
// The outlier drill is deliberately NOT closed: its baseline is every parameter
// the device measures, so a bucket switch cannot change what it shows.
watch(selectedBucket, () => {
  lotModalOpen.value = false
})

const goBack = async () => {
  await navigateTo('/ebeam/cd-sem/device-statistics')
}

onMounted(() => {
  setToolType('cd-sem')
})
</script>

<style scoped>
.comparison-section-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 0 4px;
}

.comparison-section-head__bar {
  flex: none;
  width: 4px;
  height: 40px;
  margin-top: 2px;
  border-radius: 2px;
  background: var(--sk-accent);
}

.comparison-section-head__title {
  margin: 0;
  font: 700 18px/1.15 var(--font-sans);
  letter-spacing: -0.012em;
  color: var(--sk-ink);
}

.comparison-section-head__subtitle {
  margin: 4px 0 0;
  font: 500 12px/1.4 var(--font-sans);
  color: var(--sk-ink-muted);
}
</style>
