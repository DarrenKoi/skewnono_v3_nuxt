<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow, measuredRows } from '~/utils/msrRows'
import { siteVerdicts } from '~/utils/anomaly/site'
import { SK_CHART } from '~/utils/chartPalette'

const props = defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  focusedSequence: number | null
}>()
const emit = defineEmits<{ focus: [sequence: number] }>()

const forParam = computed(() => props.rows.filter(r => r.parameter === props.parameter))

// Measured points: one marker per chip position, colored by the mean cd_value at
// that position. `name` carries a sequence at that chip so clicks can focus.
const measuredPoints = computed(() => {
  const acc = new Map<string, { x: number, y: number, sum: number, n: number, seq: number }>()
  for (const r of measuredRows(forParam.value)) {
    const xy = parseChipXY(r.chip_number)
    if (!xy) continue
    const key = `${xy[0]},${xy[1]}`
    const e = acc.get(key) ?? { x: xy[0], y: xy[1], sum: 0, n: 0, seq: r.sequence }
    e.sum += r.cd_value
    e.n += 1
    acc.set(key, e)
  }
  return [...acc.values()].map(e => ({
    name: String(e.seq),
    value: [e.x, e.y, Number((e.sum / e.n).toFixed(3))]
  }))
})

// Failures (cd_value: null) as ✕ marks — a spatial cluster of ✕ is itself a finding.
const failurePoints = computed(() =>
  forParam.value.filter(r => !isMeasuredRow(r)).map((r) => {
    const xy = parseChipXY(r.chip_number)
    return xy ? { name: String(r.sequence), value: [xy[0], xy[1]] } : null
  }).filter((p): p is { name: string, value: number[] } => p !== null)
)

// Outlier sites (abnormal|watch) as ◎ rings — same siteVerdicts as everywhere.
const outlierPoints = computed(() => {
  const flagged = new Set(
    siteVerdicts(props.rows, props.parameter)
      .filter(v => v.verdict.status === 'evaluated' && v.verdict.severity !== 'normal')
      .map(v => v.row.sequence)
  )
  return measuredPoints.value.filter(p => flagged.has(Number(p.name)))
    .map(p => ({ name: p.name, value: [p.value[0], p.value[1]] }))
})

const focusPoint = computed(() => {
  if (props.focusedSequence == null) return []
  const hit = [...measuredPoints.value, ...failurePoints.value].find(p => Number(p.name) === props.focusedSequence)
  return hit ? [{ name: hit.name, value: [hit.value[0], hit.value[1]] }] : []
})

const valueRange = computed(() => {
  const values = measuredPoints.value.map(p => p.value[2] as number)
  if (values.length === 0) return { min: 0, max: 1 }
  return { min: Math.min(...values), max: Math.max(...values) }
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      const seq = (params as { name?: string }).name
      const val = v[2] != null ? `${props.parameter}: <b>${v[2]}</b> ${props.unit}` : '측정 실패'
      return `seq ${seq} · chip (${v[0]}, ${v[1]})<br/>${val}`
    }
  },
  grid: { left: 36, right: 16, top: 16, bottom: 28, containLabel: true },
  xAxis: { type: 'value', min: -11, max: 11, splitLine: { show: true }, axisLabel: { fontSize: 10 }, name: 'chip x', nameTextStyle: { fontSize: 10 } },
  yAxis: { type: 'value', min: -11, max: 11, splitLine: { show: true }, axisLabel: { fontSize: 10 }, name: 'chip y', nameTextStyle: { fontSize: 10 } },
  visualMap: {
    min: valueRange.value.min, max: valueRange.value.max, calculable: true, orient: 'vertical',
    right: 0, top: 'center', itemHeight: 120, textStyle: { fontSize: 10 },
    dimension: 2, seriesIndex: 0, inRange: { color: [...SK_CHART.scale] }
  },
  series: [
    { type: 'scatter', symbolSize: 14, data: measuredPoints.value },
    { type: 'scatter', symbol: 'circle', symbolSize: 26, data: outlierPoints.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.bad, borderWidth: 2 }, silent: true },
    { type: 'scatter', symbol: 'pin', symbolSize: 1, data: failurePoints.value,
      label: { show: true, formatter: '✕', color: SK_CHART.bad, fontSize: 14, fontWeight: 'bold' } },
    { type: 'scatter', symbol: 'circle', symbolSize: 20, data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 }, silent: true, z: 5 }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })
</script>
