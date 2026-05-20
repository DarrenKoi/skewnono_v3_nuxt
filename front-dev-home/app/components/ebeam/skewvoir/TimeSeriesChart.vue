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
const means = computed(() => props.points.map(p => p.mean))

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const list = Array.isArray(params) ? params : [params]
      const idx = (list[0] as { dataIndex: number }).dataIndex
      const p = props.points[idx]
      if (!p) return ''
      return [
        p.label,
        `eqp: ${p.eqpId}`,
        `mean: <b>${p.mean}</b> ${props.unit}`,
        `min/max: ${p.min} / ${p.max}`,
        `std: ${p.std}`
      ].join('<br/>')
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
      data: means.value,
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
