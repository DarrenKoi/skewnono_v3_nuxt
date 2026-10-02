<template>
  <AfmCard
    icon="i-lucide-bar-chart-3"
    title="Z값 분포"
    :subject="point ? `포인트 ${point}` : undefined"
  >
    <AppLoadingState
      v-if="loading"
      variant="inline"
      class="h-full min-h-80"
      title="분포를 불러오는 중입니다."
    />
    <p
      v-else-if="profile.length === 0"
      class="flex h-full min-h-80 items-center justify-center sk-body"
    >
      분포 데이터가 없습니다.
    </p>
    <div
      v-else
      class="flex h-full flex-col gap-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <USelect
          v-model="binMethod"
          :items="binMethodItems"
          size="sm"
          class="min-w-28"
          aria-label="구간 방식"
        />
        <UInput
          v-if="binMethod === 'custom'"
          v-model.number="customBins"
          type="number"
          size="sm"
          class="w-20"
          :min="5"
          :max="200"
          aria-label="구간 수"
        />
        <USelect
          v-model="displayMode"
          :items="displayModeItems"
          size="sm"
          class="min-w-24"
          aria-label="표시 방식"
        />
        <UCheckbox
          v-model="showNormal"
          label="정규분포"
        />
        <UCheckbox
          v-model="showPercentiles"
          label="사분위"
        />
      </div>
      <AfmDetailStatStrip :items="statItems" />
      <div
        ref="chartEl"
        class="min-h-72 w-full flex-1"
      />
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { BinMethod, HistogramMode } from '~/utils/afmHistogram'

const props = defineProps<{
  profile: AfmProfilePoint[]
  point?: string
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const binMethod = ref<BinMethod>('auto')
const customBins = ref<number>(30)
const displayMode = ref<HistogramMode>('frequency')
const showNormal = ref(true)
const showPercentiles = ref(true)

const binMethodItems: { label: string, value: BinMethod }[] = [
  { label: '자동 구간', value: 'auto' },
  { label: '사용자 구간', value: 'custom' }
]
const displayModeItems: { label: string, value: HistogramMode }[] = [
  { label: '빈도', value: 'frequency' },
  { label: '밀도', value: 'density' },
  { label: '누적', value: 'cumulative' }
]

const zs = computed(() => props.profile.map(p => p.z))
const stats = computed(() => histogramStats(zs.value))
const hist = computed(() =>
  computeHistogram(zs.value, resolveBinCount(zs.value, binMethod.value, customBins.value), displayMode.value)
)

const statItems = computed(() => {
  const s = stats.value
  return [
    { label: 'μ', value: s.mean.toFixed(2) },
    { label: 'σ', value: s.stdev.toFixed(2) },
    { label: 'Q1', value: s.q1.toFixed(2) },
    { label: 'Md', value: s.median.toFixed(2) },
    { label: 'Q3', value: s.q3.toFixed(2) },
    { label: 'skew', value: s.skewness.toFixed(2) },
    { label: 'kurt', value: s.kurtosis.toFixed(2) },
    { label: 'CV', value: `${s.cv.toFixed(1)}%` }
  ]
})

const chartOption = computed<EChartsOption>(() => {
  const { centers, edges, values, binWidth } = hist.value
  const normal = showNormal.value
    ? normalCurveOverCenters(stats.value, displayMode.value, binWidth, centers)
    : []
  const quartiles = showPercentiles.value
    ? [
        { name: 'Q1', xAxis: binIndexForValue(edges, stats.value.q1) },
        { name: 'Md', xAxis: binIndexForValue(edges, stats.value.median) },
        { name: 'Q3', xAxis: binIndexForValue(edges, stats.value.q3) }
      ]
    : []

  const series: EChartsOption['series'] = [{
    type: 'bar',
    data: values,
    markLine: quartiles.length
      ? {
          symbol: 'none',
          silent: true,
          label: { ...CHART_LEGEND_LABEL, formatter: (p: { name?: string }) => p.name ?? '' },
          data: quartiles
        }
      : undefined
  }]

  if (normal.length) {
    series.push({ type: 'line', data: normal, smooth: true, symbol: 'none', z: 3 })
  }

  return {
    grid: { left: 56, right: 12, top: 28, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: centers.map(c => c.toFixed(2)),
      axisLabel: { ...CHART_AXIS_LABEL, interval: Math.max(0, Math.ceil(centers.length / 6) - 1), hideOverlap: true }
    },
    yAxis: {
      type: 'value',
      name: displayModeItems.find(item => item.value === displayMode.value)?.label,
      nameTextStyle: CHART_LEGEND_LABEL,
      axisLabel: CHART_AXIS_LABEL
    },
    series
  }
})

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
