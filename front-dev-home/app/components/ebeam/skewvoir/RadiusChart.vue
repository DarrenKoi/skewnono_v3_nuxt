<template>
  <div
    ref="chartEl"
    class="h-56 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { measuredRows } from '~/utils/msrRows'
import { polyfit, polyval } from '~/utils/polyfit'
import { SK_CHART } from '~/utils/chartPalette'

const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  degree?: number
  focusedSequence: number | null
}>(), {
  degree: 3
})
const emit = defineEmits<{ focus: [sequence: number] }>()

const rows = computed(() => measuredRows(props.rows))

// (distance-from-center, CD) per measured site for the active parameter.
// Plain numeric tuples — the polynomial fit below reads p[0]/p[1] off this.
const points = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (const row of rows.value) {
    if (row.parameter !== props.parameter) continue
    const xy = parseChipXY(row.chip_number)
    if (!xy) continue
    const radius = Math.hypot(xy[0], xy[1])
    out.push([Number(radius.toFixed(3)), row.cd_value])
  }
  return out
})

// Same rows/filter as `points`, but named per-sequence so scatter points can be
// clicked and the focused one highlighted. Kept separate so the fit above keeps
// reading `points` as plain [radius, cd] tuples.
const scatterData = computed(() => {
  const out: { name: string, value: [number, number] }[] = []
  for (const row of rows.value) {
    if (row.parameter !== props.parameter) continue
    const xy = parseChipXY(row.chip_number)
    if (!xy) continue
    const radius = Math.hypot(xy[0], xy[1])
    out.push({ name: String(row.sequence), value: [Number(radius.toFixed(3)), row.cd_value] })
  }
  return out
})

// Highlight ring for the sequence focused from another linked panel.
const focusPoint = computed(() =>
  scatterData.value.filter(p => Number(p.name) === props.focusedSequence)
)

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
      itemStyle: { color: SK_CHART.seriesSoft, opacity: 0.7 },
      data: scatterData.value
    },
    {
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: SK_CHART.brand, width: 2 },
      data: fitLine.value,
      tooltip: { show: false },
      silent: true
    },
    {
      type: 'scatter',
      symbolSize: 16,
      data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 },
      silent: true,
      z: 5
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })
</script>
