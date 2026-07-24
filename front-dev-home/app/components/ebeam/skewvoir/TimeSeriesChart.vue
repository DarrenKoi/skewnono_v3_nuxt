<template>
  <div
    ref="chartEl"
    class="h-80 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { SK_STATE } from '~/utils/chartPalette'

export interface TimeSeriesPoint {
  msr: string
  label: string
  eqpId: string
  mean: number
  min: number
  max: number
  std: number
  // Set by useSkewvoirAnalysis (trendPoints) via combineVerdicts; absent ⇒ treated as normal.
  verdict?: import('~/utils/anomaly').CombinedVerdict
}

const props = defineProps<{
  points: TimeSeriesPoint[]
  parameter: string
  unit: string
}>()

const labels = computed(() => props.points.map(p => p.label))

// min/max band rendered as two stacked lines: a transparent floor at `min`,
// then a translucent area of height (max - min) on top of it.
const floor = computed(() => props.points.map(p => p.min))
const bandHeight = computed(() => props.points.map(p => Number((p.max - p.min).toFixed(3))))
const sk = useChartPalette()

// Per-datum styling by severity (status first): insufficient grey, watch amber,
// abnormal red, normal in the theme's series color. The three severity tones
// are semantic and stay put across themes; only `normal` -- which says nothing
// beyond "this is the series" -- follows the palette.
const sevHex = computed<Record<string, string>>(() => ({
  abnormal: SK_STATE.bad,
  watch: SK_STATE.warn,
  insufficient: sk.value.muted,
  normal: sk.value.series
}))
const sevKey = (p: TimeSeriesPoint): string =>
  !p.verdict ? 'normal' : p.verdict.status === 'insufficient' ? 'insufficient' : p.verdict.severity
const meanData = computed(() =>
  props.points.map((p) => {
    const key = sevKey(p)
    const symbolSize = key === 'abnormal' ? 10 : key === 'watch' ? 9 : key === 'insufficient' ? 7 : 6
    return { value: p.mean, itemStyle: { color: sevHex.value[key] }, symbolSize }
  })
)

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const list = Array.isArray(params) ? params : [params]
      const idx = (list[0] as { dataIndex: number }).dataIndex
      const p = props.points[idx]
      if (!p) return ''
      const lines = [
        p.label,
        `eqp: ${p.eqpId}`,
        `mean: <b>${p.mean}</b> ${props.unit}`,
        `min/max: ${p.min} / ${p.max}`,
        `std: ${p.std}`
      ]
      const v = p.verdict
      if (v && (v.status === 'insufficient' || v.severity !== 'normal')) {
        // Same table and same precedence as the dot itself, so the warning text
        // can't come out red under a point that was drawn insufficient-grey.
        const color = sevHex.value[sevKey(p)]
        for (const x of v.verdicts) {
          if (x.status === 'evaluated' && x.severity === 'normal') continue
          lines.push(`<span style="color:${color}">⚠ ${x.reason}</span>`)
        }
      }
      return lines.join('<br/>')
    }
  },
  grid: { left: 48, right: 16, top: 20, bottom: 64, containLabel: true },
  xAxis: {
    type: 'category',
    data: labels.value,
    axisLabel: { fontSize: 10, rotate: 35, hideOverlap: true },
    boundaryGap: true
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true }
  },
  series: [
    {
      name: 'min',
      type: 'line',
      stack: 'band',
      data: floor.value,
      lineStyle: { opacity: 0 },
      symbol: 'none',
      silent: true,
      z: 1
    },
    {
      name: 'range',
      type: 'line',
      stack: 'band',
      data: bandHeight.value,
      lineStyle: { opacity: 0 },
      areaStyle: { color: sk.value.series, opacity: 0.12 },
      symbol: 'none',
      silent: true,
      z: 1
    },
    {
      name: 'mean',
      type: 'line',
      data: meanData.value,
      smooth: false,
      showSymbol: true,
      symbolSize: 6,
      lineStyle: { width: 2, color: sk.value.series },
      itemStyle: { color: sk.value.series },
      z: 3
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
