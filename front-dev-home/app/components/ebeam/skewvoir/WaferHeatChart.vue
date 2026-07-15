<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { SK_CHART } from '~/utils/chartPalette'

// A wafer heat map from PRE-COMPUTED points [chipX, chipY, value]. Unlike
// WaferMap (which aggregates raw MsrFileRows), this renders whatever the caller
// computed — used by Position Stack for the composite mean / variability maps.
const props = withDefaults(defineProps<{
  points: [number, number, number][]
  unit?: string
  label?: string
}>(), {
  unit: '',
  label: 'value'
})

// Axis spans the data (chip-index positions), so a wider die grid never clips.
// Symmetric + padded so the point cloud stays centred.
const axisMax = computed(() => {
  let m = 1
  for (const p of props.points) m = Math.max(m, Math.abs(p[0]), Math.abs(p[1]))
  return Math.ceil(m) + 1
})

const valueRange = computed(() => {
  const vals = props.points.map(p => p[2])
  if (vals.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  // All sites equal (e.g. a single-wafer σ map is all zeros) → min===max makes
  // ECharts' continuous visualMap divide by zero. Widen to a unit range so the
  // map renders a flat mid-color instead of a degenerate/blank scale.
  if (min === max) return { min: min - 0.5, max: max + 0.5 }
  return { min, max }
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      return `chip (${v[0]}, ${v[1]})<br/>${props.label}: <b>${v[2]}</b> ${props.unit}`
    }
  },
  grid: { left: 36, right: 16, top: 16, bottom: 28, containLabel: true },
  xAxis: {
    type: 'value',
    min: -axisMax.value,
    max: axisMax.value,
    splitLine: { show: true },
    axisLabel: { fontSize: 11 },
    name: 'chip x',
    nameTextStyle: { fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    min: -axisMax.value,
    max: axisMax.value,
    splitLine: { show: true },
    axisLabel: { fontSize: 11 },
    name: 'chip y',
    nameTextStyle: { fontSize: 11 }
  },
  visualMap: {
    min: valueRange.value.min,
    max: valueRange.value.max,
    calculable: true,
    orient: 'vertical',
    right: 0,
    top: 'center',
    itemHeight: 120,
    textStyle: { fontSize: 11 },
    // Diverging navy → tan → red (the sample's signature wafer colormap).
    inRange: { color: [...SK_CHART.scale] }
  },
  series: [{
    type: 'scatter',
    symbolSize: 14,
    data: props.points
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
