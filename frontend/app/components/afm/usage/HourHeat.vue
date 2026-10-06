<template>
  <div class="relative h-72 w-full">
    <div
      ref="chartEl"
      class="size-full"
    />
    <!-- The selected day, as a frame around its column. -->
    <div
      v-if="band"
      class="pointer-events-none absolute border-x border-(--sk-ink) opacity-50"
      :style="band"
    />
  </div>
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

const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'))

// The plot's margins, in px; the frame below is laid out from the same numbers.
// Pinned, so ECharts cannot move the plot out from under the frame.
const GRID = { left: 36, right: 76, top: 8, bottom: 28, outerBoundsMode: 'none' as const }

// Drawn in the DOM, not in the option: a rebuilt option resets the colour
// range the reader narrowed, so picking a day must leave the option alone.
const band = computed(() => dayBand(props.days, props.selected, GRID))

const chartOption = computed<EChartsOption>(() => ({
  grid: GRID,
  tooltip: {
    formatter: (params: unknown) => {
      const [day, hour, count] = (params as { value: [number, number, number] }).value
      return `${props.days[day]} ${HOURS[hour]}시<br/>측정 ${count}건`
    }
  },
  xAxis: {
    type: 'category',
    data: props.days,
    axisLabel: { ...CHART_AXIS_LABEL, formatter: (day: string) => day.slice(5).replace('-', '/'), hideOverlap: true },
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
    data: props.cells
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
