<template>
  <div
    ref="chartEl"
    class="h-80 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

export interface TimeSeriesPoint {
  msr: string
  label: string
  eqpId: string
  mean: number
  min: number
  max: number
  std: number
  // Set by AnalyzePanel from detectMadOutliers; absent ⇒ treated as not-outlier.
  outlier?: { mean: boolean, spread: boolean }
}

const props = defineProps<{
  points: TimeSeriesPoint[]
  parameter: string
  unit: string
}>()

const labels = computed(() => props.points.map(p => p.label))

// min/max band rendered as two stacked lines: a transparent floor at `min`,
// then a translucent area of height (max - min) on top of it.
const floor = computed(() => props.points.map(p => p.min))
const bandHeight = computed(() => props.points.map(p => Number((p.max - p.min).toFixed(3))))
// Per-datum styling so flagged points stand out without a second series.
// mean outlier → red+large; spread-only → amber+medium; normal → blue.
const meanData = computed(() =>
  props.points.map((p) => {
    const isMean = p.outlier?.mean ?? false
    const isSpread = p.outlier?.spread ?? false
    const color = isMean ? '#dc2626' : isSpread ? '#d97706' : '#2563eb'
    const symbolSize = isMean ? 10 : isSpread ? 9 : 6
    return { value: p.mean, itemStyle: { color }, symbolSize }
  })
)

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const list = Array.isArray(params) ? params : [params]
      const idx = (list[0] as { dataIndex: number }).dataIndex
      const p = props.points[idx]
      if (!p) return ''
      const lines = [
        p.label,
        `eqp: ${p.eqpId}`,
        `mean: <b>${p.mean}</b> ${props.unit}`,
        `min/max: ${p.min} / ${p.max}`,
        `std: ${p.std}`
      ]
      const o = p.outlier
      if (o && (o.mean || o.spread)) {
        const kind = o.mean && o.spread ? 'mean+spread' : o.mean ? 'mean' : 'spread'
        lines.push(`<span style="color:#dc2626">⚠ outlier: ${kind}</span>`)
      }
      return lines.join('<br/>')
    }
  },
  grid: { left: 48, right: 16, top: 20, bottom: 64, containLabel: true },
  xAxis: {
    type: 'category',
    data: labels.value,
    axisLabel: { fontSize: 10, rotate: 35, hideOverlap: true },
    boundaryGap: true
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true }
  },
  series: [
    {
      name: 'min',
      type: 'line',
      stack: 'band',
      data: floor.value,
      lineStyle: { opacity: 0 },
      symbol: 'none',
      silent: true,
      z: 1
    },
    {
      name: 'range',
      type: 'line',
      stack: 'band',
      data: bandHeight.value,
      lineStyle: { opacity: 0 },
      areaStyle: { color: '#3b82f6', opacity: 0.12 },
      symbol: 'none',
      silent: true,
      z: 1
    },
    {
      name: 'mean',
      type: 'line',
      data: meanData.value,
      smooth: false,
      showSymbol: true,
      symbolSize: 6,
      lineStyle: { width: 2, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      z: 3
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
