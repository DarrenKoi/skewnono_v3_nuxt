<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

// CD distribution for one parameter, in three shapes: histogram, box plot, or a
// (mirrored-density) violin. The active shape is driven by the panel's toggle.
const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  // 'Hist' | 'Box' | 'Violin' — kept as a plain string so callers can bind the
  // PanelFrame toggle value directly without an in-template type cast.
  mode?: string
}>(), {
  mode: 'Hist'
})

const BIN_COUNT = 12

const values = computed(() =>
  props.rows.filter(r => r.parameter === props.parameter).map(r => r.cd_value)
)

const mean = computed(() => {
  const v = values.value
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0
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

const quantile = (sorted: number[], q: number): number => {
  if (sorted.length === 0) return 0
  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  const next = sorted[base + 1]
  return next !== undefined ? sorted[base]! + rest * (next - sorted[base]!) : sorted[base]!
}

const boxStats = computed(() => {
  const sorted = [...values.value].sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return [
    sorted[0]!,
    quantile(sorted, 0.25),
    quantile(sorted, 0.5),
    quantile(sorted, 0.75),
    sorted[sorted.length - 1]!
  ]
})

const histOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: bins.value.centers.map(c => c.toFixed(1)),
    axisLabel: { fontSize: 10 },
    name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
    nameLocation: 'middle',
    nameGap: 26,
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: { type: 'value', axisLabel: { fontSize: 10 }, splitLine: { show: false }, name: 'count', nameTextStyle: { fontSize: 10 } },
  series: [{
    type: 'bar',
    data: bins.value.counts,
    barWidth: '90%',
    itemStyle: { color: '#7895c8', borderRadius: [2, 2, 0, 0] }
  }]
}))

const boxOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item' },
  grid: { left: 48, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: { type: 'category', data: [props.parameter], axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 }, name: props.unit, nameTextStyle: { fontSize: 10 } },
  series: [{
    type: 'boxplot',
    data: boxStats.value ? [boxStats.value] : [],
    itemStyle: { color: '#e8ddc9', borderColor: '#2752a8' }
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
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 }
    },
    yAxis: { type: 'value', axisLabel: { show: false }, splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
    series: [
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#2752a8', width: 1 }, areaStyle: { color: '#7895c8', opacity: 0.5 }, data: top },
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#2752a8', width: 1 }, areaStyle: { color: '#7895c8', opacity: 0.5 }, data: bottom }
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
