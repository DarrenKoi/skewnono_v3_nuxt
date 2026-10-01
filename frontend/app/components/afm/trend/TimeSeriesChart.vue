<template>
  <p
    v-if="points.length === 0"
    class="flex h-96 items-center justify-center sk-body"
  >
    시계열 데이터가 없습니다.
  </p>
  <div
    v-else
    ref="chartEl"
    class="h-96 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

export interface AfmTrendPoint {
  timestamp: string
  value: number
  lotId: string
  recipe: string
  filename: string
}

const props = defineProps<{
  points: AfmTrendPoint[]
  seriesName: string
  yName: string
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

// Lot, recipe and filename come from the server, so they are escaped before
// they reach the tooltip's innerHTML.
const formatTooltip = (params: unknown) => {
  const item = (Array.isArray(params) ? params[0] : params) as { marker?: string, data?: { point: AfmTrendPoint } }
  const point = item.data?.point
  if (!point) return ''
  return [
    `<strong>${item.marker ?? ''}${escapeHtml(props.seriesName)}</strong>`,
    `시간: ${escapeHtml(formatDateTimeLocal(point.timestamp))}`,
    `값: ${point.value.toFixed(3)} nm`,
    `Lot: ${escapeHtml(point.lotId)}`,
    `Recipe: ${escapeHtml(point.recipe)}`,
    `파일: ${escapeHtml(point.filename)}`
  ].join('<br>')
}

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 28, top: 36, bottom: 72 },
  tooltip: {
    trigger: 'item',
    formatter: formatTooltip
  },
  xAxis: {
    type: 'time',
    axisLabel: { ...CHART_AXIS_LABEL, formatter: '{yy}/{MM}/{dd} {HH}:{mm}' }
  },
  yAxis: {
    type: 'value',
    name: props.yName,
    nameTextStyle: CHART_LEGEND_LABEL,
    scale: true,
    axisLabel: CHART_AXIS_LABEL
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 24, bottom: 24 }
  ],
  series: [{
    name: props.seriesName,
    type: 'line',
    symbolSize: 8,
    data: props.points.map(point => ({
      value: [Date.parse(point.timestamp), point.value],
      point
    }))
  }]
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
