<template>
  <div class="flex min-w-0 flex-col gap-1">
    <p class="flex items-baseline justify-between gap-2">
      <span class="text-xs font-semibold text-(--sk-ink)">{{ label }}</span>
      <span class="sk-value-num">{{ summary }}</span>
    </p>
    <div
      ref="chartEl"
      class="h-28 w-full"
    />
    <p class="sk-meta">
      {{ note }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  label: string
  summary: string
  note: string
  kind: 'bar' | 'line'
  color: string
  points: { key: string, time: number, value: number | null }[]
  // Times to rule a vertical line at (a tip change).
  marks?: number[]
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [key: string] }>()

const sk = useChartPalette()

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 36, right: 8, top: 8, bottom: 24 },
  tooltip: {
    trigger: 'item',
    formatter: (p: unknown) => {
      const { value } = p as { value: [number, number | null] }
      return `${shortTime(value[0])}<br/>${props.label}: ${value[1] === null ? '–' : props.kind === 'bar' ? value[1] : fmt2(value[1])}`
    }
  },
  xAxis: { type: 'time', axisLabel: { ...CHART_AXIS_LABEL, formatter: '{MM}/{dd}', hideOverlap: true }, splitLine: { show: false } },
  yAxis: { type: 'value', scale: props.kind === 'line', splitNumber: 3, minInterval: props.kind === 'bar' ? 1 : undefined, axisLabel: CHART_AXIS_LABEL },
  series: [{
    type: props.kind,
    symbolSize: 6,
    barMaxWidth: 10,
    lineStyle: { color: props.color, width: 1.6 },
    markLine: {
      silent: true,
      symbol: 'none',
      label: { show: false },
      lineStyle: { type: 'solid', color: sk.value.ink, width: 1, opacity: 0.45 },
      data: (props.marks ?? []).map(time => ({ xAxis: time }))
    },
    data: props.points.map(p => ({
      value: [p.time, p.value],
      itemStyle: { color: p.key === props.selected ? sk.value.ink : props.color }
    }))
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, {
  exportName: props.exportName,
  onDataIndex: (dataIndex) => {
    const key = props.points[dataIndex]?.key
    if (key) emit('select', key)
  }
})
</script>
