<template>
  <AppLoadingState
    v-if="loading"
    variant="inline"
    class="h-96"
    title="시계열 데이터를 불러오는 중입니다."
  />
  <div
    v-else-if="series.length === 0"
    class="flex h-96 items-center justify-center text-center sk-body"
  >
    No time series data
  </div>
  <div
    v-else
    ref="chartEl"
    class="h-96 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

interface AfmTrendPoint {
  timestamp: string
  value: number
  lotId: string
  recipe: string
  filename: string
  site: string
}

interface AfmTrendSeries {
  name: string
  data: AfmTrendPoint[]
}

interface TooltipParam {
  seriesName?: string
  marker?: string
  data?: {
    value?: [number, number]
    lotId?: string
    recipe?: string
    filename?: string
    site?: string
  }
}

const props = defineProps<{
  series: AfmTrendSeries[]
  selectedColumn: string
  loading?: boolean
  exportName?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const formatTime = (timestamp: number | string) => {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return String(timestamp)
  const year = String(date.getFullYear()).slice(2)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}/${month}/${day} ${hours}:${minutes}`
}

const formatTooltip = (params: unknown) => {
  const item = (Array.isArray(params) ? params[0] : params) as TooltipParam
  const data = item.data
  const rawTime = data?.value?.[0]
  const rawValue = data?.value?.[1]
  const value = typeof rawValue === 'number' ? rawValue.toFixed(3) : '-'

  return [
    `<strong>${item.marker ?? ''}${item.seriesName ?? data?.site ?? ''}</strong>`,
    `Time: ${rawTime ? formatTime(rawTime) : '-'}`,
    `Value: ${value} nm`,
    `Lot: ${data?.lotId ?? '-'}`,
    `Recipe: ${data?.recipe ?? '-'}`,
    `File: ${data?.filename ?? '-'}`
  ].join('<br>')
}

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 54, right: 28, top: 42, bottom: 72, containLabel: true },
  tooltip: {
    trigger: 'item',
    formatter: formatTooltip
  },
  legend: {
    type: 'scroll',
    top: 0,
    right: 8,
    textStyle: { fontSize: 11 }
  },
  xAxis: {
    type: 'time',
    axisLabel: {
      fontSize: 10,
      formatter: (value: string | number) => formatTime(value)
    }
  },
  yAxis: {
    type: 'value',
    name: props.selectedColumn,
    scale: true,
    axisLabel: { fontSize: 10 }
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 24, bottom: 24 }
  ],
  series: props.series.map(siteSeries => ({
    name: siteSeries.name,
    type: 'line',
    smooth: false,
    showSymbol: true,
    symbolSize: 8,
    emphasis: { focus: 'series' as const },
    data: siteSeries.data.map(point => ({
      value: [new Date(point.timestamp).getTime(), point.value],
      lotId: point.lotId,
      recipe: point.recipe,
      filename: point.filename,
      site: point.site
    }))
  }))
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
