<template>
  <div
    ref="chartEl"
    class="h-80 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

export interface FdcTrendPoint {
  msr: string
  label: string
  eqpId: string
}

export interface FdcTrendSeries {
  name: string
  color: string
  // Signed drift in σ-units per point; null when the param is absent for an MSR.
  data: (number | null)[]
}

const props = defineProps<{
  points: FdcTrendPoint[]
  series: FdcTrendSeries[]
}>()

// Different FDC params live on wildly different scales (Brightness ≈ 128 DN,
// StigmaX ≈ 0 %), so raw values can't share one axis. We plot each param's
// *signed drift in σ-units* instead — a common, dimensionless axis where the
// warning (±2σ) and bad (±3.5σ) bands mean the same thing for every param.
const WARN = 2
const BAD = 3.5

const labels = computed(() => props.points.map(p => p.label))

const yBound = computed(() => {
  let max = BAD + 0.5
  for (const s of props.series) {
    for (const v of s.data) {
      if (v != null) max = Math.max(max, Math.abs(v) + 0.5)
    }
  }
  return Math.ceil(max)
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const list = Array.isArray(params) ? params : [params]
      const idx = (list[0] as { dataIndex: number }).dataIndex
      const p = props.points[idx]
      if (!p) return ''
      const lines = [`${p.label}`, `eqp: ${p.eqpId}`]
      for (const item of list as { seriesName: string, value: number | null, color: string }[]) {
        if (item.value == null) continue
        lines.push(
          `<span style="color:${item.color}">●</span> ${item.seriesName}: <b>${item.value.toFixed(2)}</b> σ`
        )
      }
      return lines.join('<br/>')
    }
  },
  legend: {
    type: 'scroll',
    bottom: 0,
    textStyle: { fontSize: 10 },
    itemWidth: 12,
    itemHeight: 8
  },
  grid: { left: 44, right: 16, top: 16, bottom: 56, containLabel: true },
  xAxis: {
    type: 'category',
    data: labels.value,
    axisLabel: { fontSize: 10, rotate: 35, hideOverlap: true },
    boundaryGap: true
  },
  yAxis: {
    type: 'value',
    name: 'drift (σ)',
    min: -yBound.value,
    max: yBound.value,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.4 } }
  },
  series: props.series.map((s, i) => ({
    name: s.name,
    type: 'line',
    data: s.data,
    connectNulls: true,
    smooth: false,
    showSymbol: true,
    symbolSize: 5,
    lineStyle: { width: 1.6, color: s.color },
    itemStyle: { color: s.color },
    // Attach the threshold bands once (to the first series) so they render behind.
    ...(i === 0
      ? {
          markLine: {
            silent: true,
            symbol: 'none',
            label: { fontSize: 9, formatter: '{c}σ' },
            lineStyle: { color: '#f59e0b', type: 'dashed', opacity: 0.7 },
            data: [
              { yAxis: WARN }, { yAxis: -WARN },
              { yAxis: BAD, lineStyle: { color: '#ef4444' } },
              { yAxis: -BAD, lineStyle: { color: '#ef4444' } },
              { yAxis: 0, lineStyle: { color: '#94a3b8', type: 'solid', opacity: 0.5 } }
            ]
          },
          markArea: {
            silent: true,
            itemStyle: { color: '#ef4444', opacity: 0.05 },
            data: [
              [{ yAxis: BAD }, { yAxis: yBound.value }],
              [{ yAxis: -yBound.value }, { yAxis: -BAD }]
            ]
          }
        }
      : {})
  }))
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
