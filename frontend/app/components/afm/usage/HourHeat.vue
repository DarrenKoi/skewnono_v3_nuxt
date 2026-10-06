<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

// Day × hour of day, a cell per hour that has a measurement. An hour with none
// is left blank rather than painted as the scale's low end.
const props = defineProps<{
  days: string[]
  // [day index, hour, count]
  cells: [number, number, number][]
  max: number
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [day: string] }>()

const sk = useChartPalette()

const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'))

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 36, right: 76, top: 8, bottom: 28 },
  tooltip: {
    formatter: (params: unknown) => {
      const [day, hour, count] = (params as { value: [number, number, number] }).value
      return `${props.days[day]} ${HOURS[hour]}시<br/>측정 ${count}건`
    }
  },
  xAxis: {
    type: 'category',
    data: props.days,
    axisLabel: { ...CHART_AXIS_LABEL, formatter: (day: string) => day.slice(5), hideOverlap: true },
    axisTick: { show: false },
    splitArea: { show: false }
  },
  // 00 at the top, so the day reads downwards.
  yAxis: { type: 'category', data: HOURS, inverse: true, axisLabel: { ...CHART_AXIS_LABEL, interval: 2 }, axisTick: { show: false } },
  visualMap: {
    min: 1,
    max: Math.max(props.max, 2),
    calculable: true,
    orient: 'vertical',
    right: 4,
    top: 'center',
    inRange: { color: [...SK_SCALE] },
    textStyle: CHART_LEGEND_LABEL
  },
  series: [{
    type: 'heatmap',
    animation: false,
    data: props.cells,
    // The selected day. A line, not a band: a heat map's markArea has no
    // width on a category axis.
    markLine: props.selected && props.days.includes(props.selected)
      ? {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { type: 'solid', color: sk.value.ink, width: 1, opacity: 0.45 },
          data: [{ xAxis: props.selected }]
        }
      : undefined
  }]
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
