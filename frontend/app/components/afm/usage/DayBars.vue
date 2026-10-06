<template>
  <div class="relative h-72 w-full">
    <div
      ref="chartEl"
      class="size-full"
    />
    <!-- The selected day, as a band over its column. -->
    <div
      v-if="band"
      class="pointer-events-none absolute bg-(--sk-ink) opacity-[0.08]"
      :style="band"
    />
  </div>
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

// The plot's margins, in px; the band below is laid out from the same numbers.
// Pinned: left to itself ECharts moves the plot inwards when a tick label is
// wider than its margin, and the band would no longer sit on the column. The
// left margin holds a count of four digits (`1,200`).
const GRID = { left: 56, right: 12, top: 36, bottom: 28, outerBoundsMode: 'none' as const }

// Drawn in the DOM, not in the option: useEchart rebuilds the option it is
// handed, and a rebuild resets what the reader set on the chart (a recipe
// hidden in the legend), so picking a day must leave the option alone.
const band = computed(() => dayBand(props.days, props.selected, GRID))

const chartOption = computed<EChartsOption>(() => ({
  grid: GRID,
  legend: { type: 'scroll', top: 0, left: 0, textStyle: CHART_LEGEND_LABEL },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'category',
    data: props.days,
    axisLabel: { ...CHART_AXIS_LABEL, formatter: (day: string) => day.slice(5).replace('-', '/'), hideOverlap: true },
    axisTick: { show: false }
  },
  yAxis: { type: 'value', minInterval: 1, splitNumber: 4, axisLabel: CHART_AXIS_LABEL },
  series: props.series.map(s => ({
    type: 'bar' as const,
    name: s.name,
    stack: props.stacked ? 'day' : undefined,
    barMaxWidth: 28,
    itemStyle: s.color ? { color: s.color } : undefined,
    emphasis: { focus: 'none' as const },
    data: s.values
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
