<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const props = defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
}>()

const parseChip = (chip: string): [number, number] | null => {
  const [x, y] = chip.split(',').map(part => Number(part.trim()))
  if (Number.isNaN(x) || Number.isNaN(y)) return null
  return [x!, y!]
}

// One marker per chip position, colored by the mean cd_value of the selected
// parameter at that position (multiple sequences can land on the same chip).
const points = computed(() => {
  const acc = new Map<string, { x: number, y: number, sum: number, n: number }>()
  for (const row of props.rows) {
    if (row.parameter !== props.parameter) continue
    if (row.mp_number < 0) continue
    const xy = parseChip(row.chip_number)
    if (!xy) continue
    const key = `${xy[0]},${xy[1]}`
    const entry = acc.get(key) ?? { x: xy[0], y: xy[1], sum: 0, n: 0 }
    entry.sum += row.cd_value
    entry.n += 1
    acc.set(key, entry)
  }
  return [...acc.values()].map(e => [e.x, e.y, Number((e.sum / e.n).toFixed(3))])
})

const valueRange = computed(() => {
  const values = points.value.map(p => p[2] as number)
  if (values.length === 0) return { min: 0, max: 1 }
  return { min: Math.min(...values), max: Math.max(...values) }
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const value = (params as { value: number[] }).value
      return `chip (${value[0]}, ${value[1]})<br/>${props.parameter}: <b>${value[2]}</b> ${props.unit}`
    }
  },
  grid: { left: 36, right: 16, top: 16, bottom: 28, containLabel: true },
  xAxis: {
    type: 'value',
    min: -11,
    max: 11,
    splitLine: { show: true },
    axisLabel: { fontSize: 10 },
    name: 'chip x',
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    min: -11,
    max: 11,
    splitLine: { show: true },
    axisLabel: { fontSize: 10 },
    name: 'chip y',
    nameTextStyle: { fontSize: 10 }
  },
  visualMap: {
    min: valueRange.value.min,
    max: valueRange.value.max,
    calculable: true,
    orient: 'vertical',
    right: 0,
    top: 'center',
    itemHeight: 120,
    textStyle: { fontSize: 10 },
    inRange: { color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'] }
  },
  series: [{
    type: 'scatter',
    symbolSize: 14,
    data: points.value
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
