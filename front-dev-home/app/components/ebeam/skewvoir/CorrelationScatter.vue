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
import { pearson, spearman, linearFit } from '~/utils/stats'
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

const r = computed(() => pearson(pairs.value))
const r2 = computed(() => (r.value == null ? null : r.value * r.value))
const rho = computed(() => spearman(pairs.value))
const sampleN = computed(() => pairs.value.length)

const fitLine = computed<[number, number][]>(() => {
  const pts = pairs.value
  const fit = linearFit(pts)
  if (!fit) return []
  const xs = pts.map(p => p[0])
  const min = Math.min(...xs)
  const max = Math.max(...xs)
  return [[min, fit.slope * min + fit.intercept], [max, fit.slope * max + fit.intercept]]
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
    ? {
        text: `R² = ${r2.value.toFixed(3)} · n = ${sampleN.value}${rho.value != null ? ` · ρ = ${rho.value.toFixed(3)}` : ''}`,
        right: 8,
        top: 4,
        textStyle: { fontSize: 11, color: SK_CHART.brand }
      }
    : { text: `표본 부족 · n = ${sampleN.value}`, right: 8, top: 4, textStyle: { fontSize: 11, color: SK_CHART.muted } },
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
