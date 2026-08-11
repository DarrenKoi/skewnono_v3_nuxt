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
      <div class="dashboard-surface rounded-2xl px-4 py-3.5">
        <div class="flex items-baseline gap-2.5">
          <span class="sk-panel-title">{{ text.bucketTitle }}</span>
          <span class="sk-field-name">bucket</span>
        </div>
        <div
          role="radiogroup"
          aria-label="Summary bucket"
          class="mt-2.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4"
        >
          <button
            v-for="option in bucketOptions"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="selectedBucket === option.value"
            class="flex flex-col gap-1.5 rounded-xl px-3.5 py-3 text-left ring-1 transition-colors"
            :class="selectedBucket === option.value
              ? 'bg-(--sk-accent-tint) ring-(--sk-accent)'
              : 'bg-(--sk-surface) ring-(--sk-border) hover:bg-(--sk-muted-surface)'"
            @click="selectedBucket = option.value"
          >
            <span class="flex items-center gap-2">
              <span
                class="text-base font-bold"
                :class="selectedBucket === option.value ? 'text-(--sk-accent)' : 'text-(--sk-ink)'"
              >{{ option.label }}</span>
              <UIcon
                v-if="selectedBucket === option.value"
                name="i-lucide-check"
                class="h-4 w-4 text-(--sk-accent)"
              />
            </span>
            <!-- 13.5px/1.5 — bucket 설명은 이 페이지에서 유일하게 여러 줄로 읽는
                 문장이라, 카드 값(14px)보다 살짝 작되 행간을 넉넉히 줍니다. -->
            <span class="text-[13.5px] leading-[1.5] text-pretty text-(--sk-ink-muted)">{{ option.description }}</span>
            <span class="sk-field-name">{{ option.value }}</span>
          </button>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2.5 border-t border-(--sk-border-soft) pt-3">
          <span class="text-[15px] font-bold text-(--sk-ink)">{{ text.sortTitle }}</span>
          <span class="sk-field-name">sort</span>
          <div
            role="radiogroup"
            aria-label="Sort by metric"
            class="flex flex-wrap items-center gap-1.5"
          >
            <button
              v-for="option in sortOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedSort === option.value"
              :class="[CHIP_BASE, chipClass(selectedSort === option.value)]"
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
                <div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
                  <p class="sk-panel-title">
                    {{ text.chartStackedTitle }}
                  </p>
                  <!-- 범례를 카드 헤더로 올렸습니다. ECharts 안의 범례는
                       11px 고정에 캔버스 글꼴이라 카드의 활자와 어긋났고,
                       차트 위쪽 공간을 먹어 막대를 눌렀습니다. -->
                  <div class="flex flex-wrap items-center gap-3">
                    <span
                      v-for="key in paraOrder"
                      :key="key"
                      class="inline-flex items-center gap-1.5 font-mono text-sm text-(--sk-ink-muted)"
                    >
                      <span
                        class="h-2.5 w-2.5 rounded-[3px]"
                        :style="{ background: paraPalette[key] }"
                      />
                      {{ key }}
                    </span>
                  </div>
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
                  <p class="sk-panel-title">
                    {{ text.chartAvailRecipeTitle }}
                  </p>
                  <span class="sk-field-name">avail_recipe</span>
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
          :sort="selectedSort"
          @select-lot="openLotDetail"
          @open-outliers="openOutlierDrill"
        />
        <CdsemComparisonLotDetailModal
          v-model:open="lotModalOpen"
          :row="selectedLotRow"
          :bucket="selectedBucket"
          :recipe-rows="recipeRowsForBucket"
          :recipe-params="selectedLotParams"
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
  augmentRow, buildLotVerdicts, paraTotal, recipeKey, scopeRecipesToBucket,
  type HealthAugmentedRow, type RuleSet
} from '~/utils/lotHealth'
import { sortLots, type LotSortKey } from '~/utils/lotSort'
import type { RecipeInput } from '~/utils/ruleEngine'
import { buildDeviceOutliers, groupRecipesByLot, attachProfile, type Profiled } from '~/utils/deviceProfile'
import { toOutlierDrill, type DrillDevice } from '~/utils/deviceDrill'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { paraColors, paraColorsDark, paraOrder } from '~/components/cdsem/comparison/healthTokens'
import { CHART_AXIS_LABEL, CHART_LEGEND_LABEL } from '~/utils/chartType'

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
  chartAvailRecipeTitle: '운용 레시피수',
  bucketTitle: '요약 범위',
  sortTitle: '정렬'
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
    description: '정규 Recipe만 표시합니다. 측정 중이면서 스텝명이 CD로 끝나는 Step 기준이며, CD(E)·CD(F)·CD(BENDING)처럼 괄호가 붙은 추가계측은 제외합니다.'
  },
  {
    label: 'Mother Normal',
    value: 'mother_normal_summary',
    description: 'Only Normal과 같은 Step에서 TAT에 영향을 주는 Mother 파라미터만 봅니다. para 합계·health·outlier가 모두 Mother 기준입니다.'
  },
  {
    label: 'Only Sample',
    value: 'only_sample_summary',
    description: 'Sample Recipe만 표시합니다. _S, SE Step을 선별합니다.'
  }
]

const selectedBucket = ref<SummaryBucketKey>('all_summary')

const sortOptions = [
  { label: '이름순', value: 'default' },
  { label: '파라미터', value: 'paraStack' },
  { label: '운용 레시피수', value: 'availRecipe' }
] as const

// 이 칩은 막대 차트만의 것이 아닙니다 — 아래 Lot 요약도 같은 축으로 다시
// 늘어섭니다(`:sort` prop). 정렬 규칙 자체는 utils/lotSort 에 한 벌만 있습니다.
const selectedSort = ref<LotSortKey>('default')

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

// 버킷 범위를 **한 번만** 좁힙니다. 아래 두 소비처(health / 측정 프로파일)가 같은
// 배열을 받아야 표 한 행의 열들이 서로 다른 모수집단을 말하지 않습니다.
// mother_normal 은 recipe 뿐 아니라 파라미터까지 좁히는 유일한 버킷입니다 —
// 스텝 필터는 only_normal 과 같고, 대신 mother 파라만 봅니다.
const bucketRecipes = computed(() =>
  scopeRecipesToBucket(
    recipeParams.value ?? [],
    bucketRecipeKeys.value,
    selectedBucket.value === 'mother_normal_summary'
  )
)

// bucketKeys 는 넘기지 않습니다 — bucketRecipes 가 이미 좁혀 왔습니다. 두 번
// 좁히면 어느 쪽이 진짜 범위인지 읽는 사람이 알 수 없습니다.
const lotVerdicts = computed(() =>
  buildLotVerdicts(bucketRecipes.value, rulesByFab.value ?? {})
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
const recipesByLot = computed(() => groupRecipesByLot(bucketRecipes.value))

const deviceOutliers = computed(() => buildDeviceOutliers(recipesByLot.value))

const profiledRows = computed<Profiled<HealthAugmentedRow>[]>(() =>
  augmentedRows.value.map(row => attachProfile(row, deviceOutliers.value.get(row.lot_cd)))
)

const sortedRows = computed<SummaryRow[]>(() => sortLots(rows.value, selectedSort.value))

const lotLabels = computed(() => sortedRows.value.map(row => row.lot_cd))

const mean = (xs: number[]) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0
// Sample stdev (n-1): we treat the selected devices as a sample, not the whole population.
const stdDev = (xs: number[]) => {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1))
}

const stackTotals = computed(() => sortedRows.value.map(paraTotal))
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
  // No fixed color here: every chart theme paints the tooltip on a dark
  // translucent panel (echartsThemes furniture), so a hardcoded gray like
  // #888 lands at ~2.5:1 contrast. Inheriting the theme's tooltip ink and
  // de-emphasising with opacity stays legible under every theme/mode pair.
  const header = `<div style="font-weight:600">${escapeHtml(lot)}</div>`
    + (desc
      ? '<div style="font-size:12px;opacity:0.85;margin:2px 0 6px;'
      + `max-width:320px;white-space:normal;line-height:1.45">${escapeHtml(desc)}</div>`
      : '')
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

// top:36 은 예전에 차트 안 범례가 앉던 자리였습니다. 범례를 카드 헤더로 올린
// 지금은 막대 위 값 라벨이 잘리지 않게 하는 여백입니다.
const baseGrid = { left: 48, right: 16, top: 36, bottom: 55, containLabel: true }

const baseYAxis = {
  type: 'value' as const,
  axisLabel: CHART_AXIS_LABEL,
  splitLine: { show: false }
}

const baseDataZoom = [
  { type: 'inside' as const, xAxisIndex: 0, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
  { type: 'slider' as const, xAxisIndex: 0, height: 21, bottom: 6, brushSelect: false }
]

// Deliberately keyed to colorMode, NOT to the chart theme. These marks are
// drawn onto a transparent canvas over the app's card, so what they must
// contrast with is the CARD -- and the theme picker is independent of color
// mode, so a light theme (matlab, vintage, ...) can be active in dark mode.
// Sourcing this from the theme's ink renders #262626 on a dark card.
//
// Used by the stat markLines AND the bar-top value labels: both are our own
// annotations sitting on the card, as opposed to the series colours, which
// come from the theme.
const chartInk = computed(() => colorMode.value === 'dark' ? '#e4e4e7' : '#27272a')

// Same para palette as the table's StackedBar cells (dark-aware), so the
// stacked chart, table, and detail modal all read as one color system.
const paraPalette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const sigmaLineStyle = computed(() => ({
  type: 'dotted' as const,
  color: chartInk.value,
  width: 1,
  opacity: 0.55
}))

// 막대 위 값. hideOverlap 은 series 쪽 labelLayout 이 맡습니다 — lot 이 많아
// 축이 빽빽해지면 라벨이 서로 밟고 올라서는 대신 조용히 사라집니다.
const barValueLabel = computed(() => ({
  show: true,
  position: 'top' as const,
  ...CHART_AXIS_LABEL,
  fontWeight: 600 as const,
  color: chartInk.value
}))

const buildStatsMarkLine = (avg: number, sd: number) => ({
  symbol: 'none' as const,
  silent: true,
  lineStyle: { type: 'dashed' as const, color: chartInk.value, width: 1.5 },
  label: {
    ...CHART_LEGEND_LABEL,
    color: chartInk.value,
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

const buildCategoryAxis = () => ({
  type: 'category' as const,
  data: lotLabels.value,
  axisLabel: { ...CHART_AXIS_LABEL, interval: 0, rotate: lotLabels.value.length > 8 ? 35 : 0 }
})

// 범례는 카드 헤더가 그립니다(위 template) — 여기서 legend 를 다시 켜면 같은
// 네 항목이 두 벌 나옵니다.
const stackedOption = computed<EChartsOption>(() => ({
  tooltip: baseTooltip,
  grid: baseGrid,
  dataZoom: baseDataZoom,
  xAxis: buildCategoryAxis(),
  yAxis: baseYAxis,
  series: paraOrder.map((key, index) => ({
    name: key,
    type: 'bar' as const,
    stack: 'para',
    itemStyle: { color: paraPalette.value[key] },
    data: sortedRows.value.map(r => r[key]),
    // 값 라벨은 마지막 조각에만 답니다. 조각마다 달면 스택 안에 숫자 넷이
    // 겹쳐 쌓이고, 정작 읽고 싶은 것은 기둥 전체의 합계입니다. 마지막 조각의
    // 위쪽이 곧 스택의 꼭대기이므로 position:'top' 이 합계 자리에 놓입니다.
    ...(index === paraOrder.length - 1
      ? {
          markLine: buildStatsMarkLine(avgStackTotal.value, stdStackTotal.value),
          label: {
            ...barValueLabel.value,
            formatter: ({ dataIndex }: { dataIndex: number }) => String(stackTotals.value[dataIndex] ?? '')
          },
          labelLayout: { hideOverlap: true }
        }
      : {})
  }))
}))

const availRecipeOption = computed<EChartsOption>(() => ({
  tooltip: baseTooltip,
  grid: baseGrid,
  dataZoom: baseDataZoom,
  xAxis: buildCategoryAxis(),
  yAxis: baseYAxis,
  series: [{
    name: 'avail_recipe',
    type: 'bar',
    // No itemStyle.color: sole series, so ECharts already assigns palette[0].
    data: sortedRows.value.map(r => r.avail_recipe),
    label: barValueLabel.value,
    labelLayout: { hideOverlap: true },
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

// 모달의 CSV 내보내기가 쓰는 파라미터. drill 과 **같은 map** 에서 꺼냅니다 —
// 이미 버킷 범위로 좁혀진 recipesByLot 이라, 파일이 화면의 health·outlier 와
// 다른 모집단을 말할 수 없습니다. 열려 있는 lot 것만 넘겨 모달은 좁히는 일을
// 하지 않습니다.
const selectedLotParams = computed<RecipeInput[]>(() => {
  const lotCd = selectedLotRow.value?.lot_cd
  return lotCd ? recipesByLot.value.get(lotCd) ?? [] : []
})

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openOutlierDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const result = deviceOutliers.value.get(lot_cd)
  if (!result) return
  activeDrill.value = toOutlierDrill(lot_cd, recipes[0]?.ctn_desc ?? '', recipes, result)
  drillOpen.value = true
}

// 버킷이 바뀌면 열려 있던 두 오버레이를 모두 닫습니다 — 둘 다 버킷 범위의
// 숫자를 들고 있어서, 열어 둔 채로 두면 이전 버킷의 값을 계속 보여줍니다.
//
// drill 은 예전에 일부러 열어 두었습니다("기준선이 디바이스가 측정하는 모든
// 파라미터라 버킷이 바뀌어도 보여줄 것이 안 변한다"). 2026-08-04 부터 중앙값·
// outlier 도 버킷 범위로 계산하므로 그 전제가 더는 참이 아닙니다.
watch(selectedBucket, () => {
  lotModalOpen.value = false
  drillOpen.value = false
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

/* 400, not 500: Spoqa 의 획은 작을수록 뭉치므로 한글은 굵기 대신 크기로
   읽히게 합니다 (12px/500 → 14px/400). */
.comparison-section-head__subtitle {
  margin: 4px 0 0;
  font: 400 14px/1.45 var(--font-sans);
  color: var(--sk-ink-muted);
}
</style>
