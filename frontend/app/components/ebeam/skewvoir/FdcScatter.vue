<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { FdcStatus } from '~/composables/useMsrFileApi'

export interface FdcScatterPoint {
  x: number
  y: number
  label: string
  eqpId: string
  status: FdcStatus
}

const props = defineProps<{
  points: FdcScatterPoint[]
  xName: string
  xUnit: string
  yName: string
  yUnit: string
  // Optional least-squares fit line endpoints [[x0,y0],[x1,y1]].
  fit?: [[number, number], [number, number]] | null
}>()

const STATUS_COLOR: Record<FdcStatus, string> = {
  ok: '#22c55e',
  warning: '#f59e0b',
  bad: '#ef4444'
}

const data = computed(() =>
  props.points.map(p => ({
    value: [p.x, p.y],
    itemStyle: { color: STATUS_COLOR[p.status] },
    _label: p.label,
    _eqp: p.eqpId
  }))
)

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = params as unknown as { data: { _label: string, _eqp: string, value: number[] } }
      const [x, y] = p.data.value
      return [
        p.data._label,
        `eqp: ${p.data._eqp}`,
        `${props.xName}: <b>${x}</b> ${props.xUnit}`,
        `${props.yName}: <b>${y}</b> ${props.yUnit}`
      ].join('<br/>')
    }
  },
  grid: { left: 48, right: 18, top: 18, bottom: 44, containLabel: true },
  xAxis: {
    type: 'value',
    scale: true,
    name: props.xUnit ? `${props.xName} (${props.xUnit})` : props.xName,
    nameLocation: 'middle',
    nameGap: 26,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true, lineStyle: { opacity: 0.3 } }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.yUnit ? `${props.yName} (${props.yUnit})` : props.yName,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true, lineStyle: { opacity: 0.3 } }
  },
  series: [
    {
      type: 'scatter',
      symbolSize: 11,
      data: data.value,
      emphasis: { focus: 'self' }
    },
    ...(props.fit
      ? [{
          type: 'line' as const,
          data: props.fit,
          symbol: 'none',
          silent: true,
          lineStyle: { color: '#64748b', width: 1.4, type: 'dashed' as const },
          z: 1
        }]
      : [])
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
