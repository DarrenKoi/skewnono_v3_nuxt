<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-bar-chart-3"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Z-value distribution
          </h2>
        </div>
        <p
          v-if="stats.count"
          class="sk-meta tabular-nums"
        >
          μ={{ stats.mean.toFixed(2) }} · σ={{ stats.stdev.toFixed(2) }}
          · Q1={{ stats.q1.toFixed(2) }} · Md={{ stats.median.toFixed(2) }} · Q3={{ stats.q3.toFixed(2) }}
          · skew={{ stats.skewness.toFixed(2) }} · kurt={{ stats.kurtosis.toFixed(2) }} · CV={{ stats.cv.toFixed(1) }}%
        </p>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-60 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading distribution…
    </div>
    <div
      v-else-if="profile.length === 0"
      class="flex h-60 items-center justify-center text-center sk-body"
    >
      No distribution data
    </div>
    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <USelect
          v-model="binMethod"
          :items="binMethodItems"
          size="xs"
          class="min-w-28"
          aria-label="Bin method"
        />
        <UInput
          v-if="binMethod === 'custom'"
          v-model.number="customBins"
          type="number"
          size="xs"
          class="w-20"
          :min="5"
          :max="200"
          aria-label="Bin count"
        />
        <USelect
          v-model="displayMode"
          :items="displayModeItems"
          size="xs"
          class="min-w-28"
          aria-label="Display mode"
        />
        <UCheckbox
          v-model="showNormal"
          label="Normal"
          size="xs"
        />
        <UCheckbox
          v-model="showPercentiles"
          label="Quartiles"
          size="xs"
        />
      </div>
      <div
        ref="chartEl"
        class="h-60 w-full"
      />
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { BinMethod, HistogramMode } from '~/utils/afmHistogram'

const props = defineProps<{
  profile: AfmProfilePoint[]
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
  { label: 'Auto bins', value: 'auto' },
  { label: 'Custom bins', value: 'custom' }
]
const displayModeItems: { label: string, value: HistogramMode }[] = [
  { label: 'Frequency', value: 'frequency' },
  { label: 'Density', value: 'density' },
  { label: 'Cumulative', value: 'cumulative' }
]

const zs = computed(() => props.profile.map(p => p.z))
const stats = computed(() => histogramStats(zs.value))
const binCount = computed(() => resolveBinCount(zs.value, binMethod.value, customBins.value))
const hist = computed(() => computeHistogram(zs.value, binCount.value, displayMode.value))

const centerLabels = computed(() => hist.value.centers.map(c => c.toFixed(2)))

const normalSeriesData = computed(() =>
  showNormal.value
    ? normalCurveOverCenters(stats.value, displayMode.value, hist.value.binWidth, hist.value.centers)
    : []
)

const percentileMarks = computed(() => {
  if (!showPercentiles.value || !stats.value.count) return []
  const edges = hist.value.edges
  return [
    { name: 'Q1', xAxis: binIndexForValue(edges, stats.value.q1) },
    { name: 'Md', xAxis: binIndexForValue(edges, stats.value.median) },
    { name: 'Q3', xAxis: binIndexForValue(edges, stats.value.q3) }
  ]
})

const yAxisName = computed(() =>
  displayMode.value === 'density'
    ? 'Density'
    : displayMode.value === 'cumulative' ? 'Cumulative' : 'Frequency'
)

const chartOption = computed<EChartsOption>(() => {
  const series: EChartsOption['series'] = [{
    type: 'bar',
    data: hist.value.values,
    itemStyle: { borderRadius: [3, 3, 0, 0] },
    markLine: percentileMarks.value.length
      ? {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed', color: '#94a3b8' },
          label: { fontSize: 9, formatter: (p: { name?: string }) => p.name ?? '' },
          data: percentileMarks.value
        }
      : undefined
  }]

  if (normalSeriesData.value.length) {
    series.push({
      type: 'line',
      data: normalSeriesData.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#ef4444', width: 2 },
      z: 3
    })
  }

  return {
    grid: { left: 46, right: 12, top: 16, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: centerLabels.value,
      axisLabel: { fontSize: 10, interval: Math.max(0, Math.ceil(centerLabels.value.length / 8) - 1) }
    },
    yAxis: {
      type: 'value',
      name: yAxisName.value,
      nameTextStyle: { fontSize: 9 },
      axisLabel: { fontSize: 10 }
    },
    series
  }
})

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
