<template>
  <div class="flex flex-col">
    <div class="mb-1 text-center sk-eyebrow">
      {{ title }}
    </div>
    <div
      v-if="values.length === 0"
      class="flex h-80 items-center justify-center sk-body"
    >
      측정을 선택하세요.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-80 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

// Degree-profile line/scatter: x is the angular position (0~360°), y the metric
// value. Used for reso_detector, whose tiny magnitudes (~0.005) read better on
// a cartesian axis than as a radar blob squeezed against the center.
const props = defineProps<{
  title: string
  // Degree keys as strings ("0.0".."337.5"), numerically ordered by the parent.
  angles: string[]
  values: number[]
  colorIndex: number
  // Fixed y scale (set per-metric by the parent across the filtered docs) so
  // switching timestamps doesn't rescale the axis under the reader.
  min: number
  max: number
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const { palette } = useEchartsTheme()
const color = computed(() => palette.value[props.colorIndex] ?? palette.value[0] ?? '#6366f1')

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 64, right: 16, top: 12, bottom: 28 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'line' },
    valueFormatter: v => (typeof v === 'number' ? v.toFixed(4) : String(v))
  },
  xAxis: {
    type: 'value',
    min: 0,
    max: 360,
    interval: 45,
    axisLabel: { fontSize: 10, formatter: '{value}°' }
  },
  yAxis: {
    type: 'value',
    min: props.min,
    max: props.max,
    axisLabel: { fontSize: 10 }
  },
  series: [
    {
      type: 'line',
      showSymbol: true,
      symbolSize: 6,
      lineStyle: { width: 1.5, color: color.value },
      itemStyle: { color: color.value },
      data: props.angles
        .map((a, i) => [Number(a), props.values[i] ?? NaN] as [number, number])
        .filter(([, v]) => Number.isFinite(v))
    }
  ]
}))

useEchart(chartEl, chartOption)
</script>
