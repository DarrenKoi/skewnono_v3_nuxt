<template>
  <EbeamHardwareChartFrame
    :title="title"
    :empty="values.length === 0"
    :option="chartOption"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  title: string
  angles: string[]
  values: number[]
  // Index into the active theme palette (rather than a hardcoded hex), so the
  // radar honors the theme picked in settings. Sharpness/Noise pass 0/1 to stay
  // visually distinct, mirroring the trend chart's avg/3σ series colors.
  colorIndex: number
  // Fixed radial scale (set per-metric by the parent). A wide, fixed range
  // keeps a tight profile reading as a near-circle instead of an exaggerated
  // shape; tune these per metric/circumstance from BsmPanel.
  min: number
  max: number
}>()

const { palette } = useEchartsTheme()
const color = computed(() => palette.value[props.colorIndex] ?? palette.value[0] ?? '#6366f1')

const chartOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    valueFormatter: value => (typeof value === 'number' ? value.toFixed(3) : String(value))
  },
  radar: {
    indicator: props.angles.map(angle => ({
      name: `${angle}°`,
      min: props.min,
      max: props.max
    })),
    radius: '80%',
    axisName: { fontSize: 9, color: 'var(--sk-ink-muted)' },
    splitNumber: 4
  },
  series: [
    {
      type: 'radar',
      symbolSize: 3,
      lineStyle: { width: 2, color: color.value },
      itemStyle: { color: color.value },
      areaStyle: { opacity: 0.12, color: color.value },
      data: [{ value: props.values, name: props.title }]
    }
  ]
}))
</script>
