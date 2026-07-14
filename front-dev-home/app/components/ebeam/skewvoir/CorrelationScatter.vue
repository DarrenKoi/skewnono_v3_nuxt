<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { validRows } from '~/utils/msrRows'
import { polyfit, polyval } from '~/utils/polyfit'
import { SK_CHART } from '~/utils/chartPalette'

// Param-vs-param correlation within one measurement. Pairs the two parameters'
// CD values by site key (chip + sequence), draws the scatter + a linear fit, and
// reports R² (how much of Y's variation the linear relation with X explains).
const props = defineProps<{
  rows: MsrFileRow[]
  paramX: string
  paramY: string
  unitX: string
  unitY: string
}>()

const rows = computed(() => validRows(props.rows))

const pairs = computed<[number, number][]>(() => {
  const xBySite = new Map<string, number>()
  for (const r of rows.value) {
    if (r.parameter === props.paramX) xBySite.set(`${r.chip_number}#${r.sequence}`, r.cd_value)
  }
  const out: [number, number][] = []
  for (const r of rows.value) {
    if (r.parameter !== props.paramY) continue
    const x = xBySite.get(`${r.chip_number}#${r.sequence}`)
    if (x != null) out.push([x, r.cd_value])
  }
  return out
})

// Pearson r², the share of Y's variance explained by the linear fit on X.
const r2 = computed(() => {
  const pts = pairs.value
  const n = pts.length
  if (n < 2) return null
  const mx = pts.reduce((a, p) => a + p[0], 0) / n
  const my = pts.reduce((a, p) => a + p[1], 0) / n
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (const [x, y] of pts) {
    sxy += (x - mx) * (y - my)
    sxx += (x - mx) ** 2
    syy += (y - my) ** 2
  }
  if (sxx === 0 || syy === 0) return null
  const r = sxy / Math.sqrt(sxx * syy)
  return r * r
})

const fitLine = computed<[number, number][]>(() => {
  const pts = pairs.value
  if (pts.length < 2) return []
  const coeffs = polyfit(pts.map(p => p[0]), pts.map(p => p[1]), 1)
  if (!coeffs) return []
  const xs = pts.map(p => p[0])
  const min = Math.min(...xs)
  const max = Math.max(...xs)
  return [[min, polyval(coeffs, min)], [max, polyval(coeffs, max)]]
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      return `${props.paramX}: <b>${v[0]}</b><br/>${props.paramY}: <b>${v[1]}</b>`
    }
  },
  title: r2.value != null
    ? { text: `R² = ${r2.value.toFixed(3)}`, right: 8, top: 4, textStyle: { fontSize: 11, color: SK_CHART.brand } }
    : undefined,
  grid: { left: 44, right: 16, top: 24, bottom: 36, containLabel: true },
  xAxis: {
    type: 'value',
    scale: true,
    name: props.unitX ? `${props.paramX} (${props.unitX})` : props.paramX,
    nameLocation: 'middle',
    nameGap: 24,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unitY ? `${props.paramY} (${props.unitY})` : props.paramY,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  series: [
    {
      type: 'scatter',
      symbolSize: 7,
      itemStyle: { color: SK_CHART.seriesSoft, opacity: 0.7 },
      data: pairs.value
    },
    {
      type: 'line',
      smooth: false,
      showSymbol: false,
      lineStyle: { color: SK_CHART.brand, width: 2 },
      data: fitLine.value,
      tooltip: { show: false },
      silent: true
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
