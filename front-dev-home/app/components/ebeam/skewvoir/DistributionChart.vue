<template>
  <div
    ref="chartEl"
    class="w-full"
    :class="heightClass"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { paramValues } from '~/utils/msrRows'
import { mean as meanOf, quantileSorted, iqrFences } from '~/utils/stats'
import { SK_CHART } from '~/utils/chartPalette'

// CD distribution for one parameter, in three shapes: histogram, box plot, or a
// (mirrored-density) violin. The active shape is driven by the panel's toggle.
const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  // 'Hist' | 'Box' | 'Violin' — kept as a plain string so callers can bind the
  // PanelFrame toggle value directly without an in-template type cast.
  mode?: string
  // Chart height utility. Defaults to a fixed h-72; the dashboard passes h-full
  // so the chart fills a flex panel.
  heightClass?: string
}>(), {
  mode: 'Hist',
  heightClass: 'h-72'
})

const BIN_COUNT = 12

const values = computed(() => paramValues(props.rows, props.parameter))

// null, not 0: an empty parameter has no mean to mark. A markline/label
// consumer must suppress rendering on null rather than plotting a fabricated
// CD = 0 — see governing principle in app/utils/msrRows.ts / stats.ts.
const mean = computed<number | null>(() => {
  const v = values.value
  return v.length ? meanOf(v) : null
})

// Shared binning for histogram + violin.
const bins = computed(() => {
  const vals = values.value
  if (vals.length === 0) return { centers: [] as number[], counts: [] as number[] }
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const width = span / BIN_COUNT
  const counts = new Array(BIN_COUNT).fill(0)
  for (const v of vals) {
    const idx = Math.min(BIN_COUNT - 1, Math.floor((v - min) / width))
    counts[idx] += 1
  }
  const centers = counts.map((_, i) => min + width * (i + 0.5))
  return { centers, counts }
})

// Five-number summary with Tukey-fenced whiskers. Unlike the MDC fleet boxplot
// (boxplotStats.ts), a CD distribution has hundreds of sites, so fencing surfaces
// genuine outliers instead of hiding real tools.
const boxStats = computed(() => {
  const sorted = [...values.value].sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const f = iqrFences(sorted)!
  const inliers = sorted.filter(v => v >= f.lower && v <= f.upper)
  return [
    inliers[0] ?? sorted[0]!,
    f.q1,
    quantileSorted(sorted, 0.5),
    f.q3,
    inliers[inliers.length - 1] ?? sorted[sorted.length - 1]!
  ]
})

const histOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: bins.value.centers.map(c => c.toFixed(1)),
    axisLabel: { fontSize: 11 },
    name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
    nameLocation: 'middle',
    nameGap: 26,
    nameTextStyle: { fontSize: 11 }
  },
  yAxis: { type: 'value', axisLabel: { fontSize: 11 }, splitLine: { show: false }, name: 'count', nameTextStyle: { fontSize: 11 } },
  series: [{
    type: 'bar',
    data: bins.value.counts,
    barWidth: '90%',
    itemStyle: { color: SK_CHART.seriesSoft, borderRadius: [2, 2, 0, 0] }
  }]
}))

const boxOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item' },
  grid: { left: 48, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: { type: 'category', data: [props.parameter], axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 11 }, name: props.unit, nameTextStyle: { fontSize: 11 } },
  series: [{
    type: 'boxplot',
    data: boxStats.value ? [boxStats.value] : [],
    itemStyle: { color: SK_CHART.sand, borderColor: SK_CHART.series }
  }]
}))

// Violin: mirror the binned density around the value axis (±count/2).
const violinOption = computed<EChartsOption>(() => {
  const { centers, counts } = bins.value
  const top = centers.map((c, i) => [c, counts[i]! / 2])
  const bottom = centers.map((c, i) => [c, -counts[i]! / 2])
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
    xAxis: {
      type: 'value',
      scale: true,
      name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
      nameLocation: 'middle',
      nameGap: 24,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 }
    },
    yAxis: { type: 'value', axisLabel: { show: false }, splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
    series: [
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: SK_CHART.series, width: 1 }, areaStyle: { color: SK_CHART.seriesSoft, opacity: 0.5 }, data: top },
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: SK_CHART.series, width: 1 }, areaStyle: { color: SK_CHART.seriesSoft, opacity: 0.5 }, data: bottom }
    ]
  }
})

const option = computed<EChartsOption>(() => {
  if (props.mode === 'Box') return boxOption.value
  if (props.mode === 'Violin') return violinOption.value
  return histOption.value
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)

defineExpose({ mean })
</script>
