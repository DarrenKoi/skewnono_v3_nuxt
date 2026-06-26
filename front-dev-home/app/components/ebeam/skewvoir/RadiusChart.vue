<template>
  <div
    ref="chartEl"
    class="h-56 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { polyfit, polyval } from '~/utils/polyfit'

const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  degree?: number
}>(), {
  degree: 3
})

const parseChip = (chip: string): [number, number] | null => {
  const [x, y] = chip.split(',').map(part => Number(part.trim()))
  if (Number.isNaN(x) || Number.isNaN(y)) return null
  return [x!, y!]
}

// (distance-from-center, CD) per measured site for the active parameter.
const points = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (const row of props.rows) {
    if (row.parameter !== props.parameter) continue
    if (row.mp_number < 0) continue
    const xy = parseChip(row.chip_number)
    if (!xy) continue
    const radius = Math.hypot(xy[0], xy[1])
    out.push([Number(radius.toFixed(3)), row.cd_value])
  }
  return out
})

// Sampled polynomial fit line across the radius span.
const fitLine = computed<[number, number][]>(() => {
  if (points.value.length < props.degree + 1) return []
  const xs = points.value.map(p => p[0])
  const ys = points.value.map(p => p[1])
  const coeffs = polyfit(xs, ys, props.degree)
  if (!coeffs) return []
  const maxR = Math.max(...xs)
  const steps = 40
  return Array.from({ length: steps + 1 }, (_, i) => {
    const x = (maxR * i) / steps
    return [Number(x.toFixed(3)), Number(polyval(coeffs, x).toFixed(4))] as [number, number]
  })
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      return `r ${v[0]}<br/>${props.parameter}: <b>${v[1]}</b> ${props.unit}`
    }
  },
  grid: { left: 44, right: 16, top: 16, bottom: 32, containLabel: true },
  xAxis: {
    type: 'value',
    min: 0,
    name: 'distance from center',
    nameLocation: 'middle',
    nameGap: 22,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit || 'CD',
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  series: [
    {
      type: 'scatter',
      symbolSize: 7,
      itemStyle: { color: '#7895c8', opacity: 0.7 },
      data: points.value
    },
    {
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#b21f24', width: 2 },
      data: fitLine.value,
      tooltip: { show: false },
      silent: true
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
