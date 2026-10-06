<template>
  <div
    ref="chartEl"
    class="h-40 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

// One recipe's measurements per day over its own span. The colour is left to
// the chart theme; nothing here depends on a selection.
const props = defineProps<{
  days: { day: string, count: number }[]
  exportName: string
}>()

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 32, right: 8, top: 8, bottom: 24 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (p: unknown) => {
      const [bar] = p as { name: string, value: number }[]
      return bar ? `${bar.name}<br/>측정 ${bar.value}건` : ''
    }
  },
  xAxis: {
    type: 'category',
    data: props.days.map(d => d.day),
    axisLabel: { ...CHART_AXIS_LABEL, formatter: (day: string) => day.slice(5).replace('-', '/'), hideOverlap: true },
    axisTick: { show: false }
  },
  yAxis: { type: 'value', minInterval: 1, splitNumber: 3, axisLabel: CHART_AXIS_LABEL },
  series: [{ type: 'bar', barMaxWidth: 14, data: props.days.map(d => d.count) }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
