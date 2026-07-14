<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { measuredRows } from '~/utils/msrRows'
import { pearson, spearman, fitLine } from '~/utils/stats'
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

const rows = computed(() => measuredRows(props.rows))

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

// pearson returns null for TWO distinct reasons: n < 3 (too few pairs) or zero
// variance on either axis (plenty of pairs, but a constant CD). Conflating them
// under "표본 부족" would lie when n is large — label each honestly.
const noAnswerLabel = computed(() => (sampleN.value < 3 ? '표본 부족' : '분산 없음'))

const fitLinePoints = computed<[number, number][]>(() => fitLine(pairs.value) ?? [])

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
    : { text: `${noAnswerLabel.value} · n = ${sampleN.value}`, right: 8, top: 4, textStyle: { fontSize: 11, color: SK_CHART.muted } },
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
      data: fitLinePoints.value,
      tooltip: { show: false },
      silent: true
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
