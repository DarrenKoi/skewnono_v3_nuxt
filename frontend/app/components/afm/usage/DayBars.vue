<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

// Bars per calendar day of the window, one group or one stack per day. A click
// anywhere in a day's column selects it — an idle day has no bar to hit.
const props = defineProps<{
  days: string[]
  // A series with no colour takes the theme's next one.
  series: { name: string, values: number[], color?: string }[]
  stacked?: boolean
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [day: string] }>()

const sk = useChartPalette()

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 40, right: 12, top: 36, bottom: 28 },
  legend: { type: 'scroll', top: 0, left: 0, textStyle: CHART_LEGEND_LABEL },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'category',
    data: props.days,
    axisLabel: { ...CHART_AXIS_LABEL, formatter: (day: string) => day.slice(5), hideOverlap: true },
    axisTick: { show: false }
  },
  yAxis: { type: 'value', minInterval: 1, splitNumber: 4, axisLabel: CHART_AXIS_LABEL },
  series: props.series.map((s, i) => ({
    type: 'bar' as const,
    name: s.name,
    stack: props.stacked ? 'day' : undefined,
    barMaxWidth: 28,
    itemStyle: s.color ? { color: s.color } : undefined,
    emphasis: { focus: 'none' as const },
    data: s.values,
    // The selected day, as a band behind its column.
    markArea: i === 0 && props.selected && props.days.includes(props.selected)
      ? {
          silent: true,
          itemStyle: { color: sk.value.ink, opacity: 0.08 },
          data: [[{ xAxis: props.selected }, { xAxis: props.selected }]]
        }
      : undefined
  }))
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, {
  exportName: props.exportName,
  onGridClick: ({ x }) => {
    const day = props.days[Math.round(x)]
    if (day) emit('select', day)
  }
})
</script>
