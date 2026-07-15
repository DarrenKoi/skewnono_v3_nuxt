<template>
  <div
    ref="chartEl"
    class="h-full w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow, measuredRows } from '~/utils/msrRows'
import { SK_CHART } from '~/utils/chartPalette'
import { stagePosMm, dieCenterMm, type WaferGeometry } from '~/utils/waferGeometry'

const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  geo: WaferGeometry
  focusedSequence: number | null
  outlierSeqs: number[]
  /** 'Sites' = colored dots at stage positions; 'Field' = filled die tiles. */
  mode?: 'Sites' | 'Field'
}>(), {
  mode: 'Sites'
})
const emit = defineEmits<{
  focus: [sequence: number]
  /** Color-scale range (min/max of the plotted values) for the panel's legend. */
  rangechange: [range: { min: number, max: number }]
}>()

const forParam = computed(() => props.rows.filter(r => r.parameter === props.parameter))

// Aggregate measured rows by die (chip_number). Store the die grid index (for the
// tile position) AND a representative physical stage position in mm (for the dot),
// plus the full sequence set so ring lookups test every sequence on the die.
interface Die { col: number, row: number, sx: number, sy: number, sum: number, n: number, seq: number, seqs: Set<number> }
const dies = computed(() => {
  const acc = new Map<string, Die>()
  for (const r of measuredRows(forParam.value)) {
    const chip = parseChipXY(r.chip_number)
    const pos = stagePosMm(r.stage_coordinate, props.geo)
    if (!chip || !pos) continue
    const e = acc.get(r.chip_number)
      ?? { col: chip[0], row: chip[1], sx: pos[0], sy: pos[1], sum: 0, n: 0, seq: r.sequence, seqs: new Set<number>() }
    e.sum += r.cd_value
    e.n += 1
    e.seqs.add(r.sequence)
    acc.set(r.chip_number, e)
  }
  return [...acc.values()]
})

// Sites dots — at the measured physical position (mm from centre).
const sitePoints = computed(() =>
  dies.value.map(e => ({ name: String(e.seq), value: [e.sx, e.sy, Number((e.sum / e.n).toFixed(3))] }))
)

// Field tiles — at the die-grid centre so cells align to the pitch.
const tilePoints = computed(() =>
  dies.value.map((e) => {
    const [cx, cy] = dieCenterMm(e.col, e.row, props.geo)
    return { name: String(e.seq), value: [cx, cy, Number((e.sum / e.n).toFixed(3))] }
  })
)

// Failures (cd_value: null) as ✕ marks at their physical position.
const failurePoints = computed(() =>
  forParam.value.filter(r => !isMeasuredRow(r)).map((r) => {
    const pos = stagePosMm(r.stage_coordinate, props.geo)
    return pos ? { name: String(r.sequence), value: [pos[0], pos[1]] } : null
  }).filter((p): p is { name: string, value: number[] } => p !== null)
)

// ◎ ring on any die holding a sequence flagged by the single overview source.
const outlierPoints = computed(() => {
  const flagged = new Set(props.outlierSeqs)
  return dies.value
    .filter(e => [...e.seqs].some(s => flagged.has(s)))
    .map(e => ({ name: String(e.seq), value: [e.sx, e.sy] }))
})

// Focus ring at the focused sequence's die (measured) or its ✕ point (failure).
const focusPoint = computed(() => {
  const fseq = props.focusedSequence
  if (fseq == null) return []
  const hit = dies.value.find(e => e.seqs.has(fseq))
  if (hit) return [{ name: String(hit.seq), value: [hit.sx, hit.sy] }]
  const fail = failurePoints.value.find(p => Number(p.name) === fseq)
  return fail ? [{ name: fail.name, value: [fail.value[0], fail.value[1]] }] : []
})

const valueRange = computed(() => {
  const values = sitePoints.value.map(p => p.value[2] as number)
  if (values.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  return min === max ? { min: min - 0.5, max: max + 0.5 } : { min, max }
})

// Publish the color-scale range so the panel can draw the legend outside the chart.
watch(valueRange, r => emit('rangechange', r), { immediate: true })

// Wafer boundary from exe_detail_info (wafer_size/2, in mm). Symmetric, equal
// axes + a square body keep it a true circle. Axis just clears the edge.
const waferRadius = computed(() => props.geo.radiusMm || 150)
const axisMax = computed(() => waferRadius.value * 1.03)

const waferOutline = computed<[number, number][]>(() => {
  const R = waferRadius.value
  const steps = 120
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = (i / steps) * Math.PI * 2
    return [Number((R * Math.cos(t)).toFixed(3)), Number((R * Math.sin(t)).toFixed(3))] as [number, number]
  })
})

// Field mode draws each measured die as a pitch-sized rect, colored by visualMap.
// api.coord() converts the cell corners to pixels so tiles scale with zoom.
const renderTile = (params: unknown, api: {
  value: (i: number) => number
  coord: (d: number[]) => number[]
  visual: (k: string) => string
}) => {
  const hx = (props.geo.pitchXmm || waferRadius.value / 30) / 2
  const hy = (props.geo.pitchYmm || waferRadius.value / 30) / 2
  const cx = api.value(0)
  const cy = api.value(1)
  const p0 = api.coord([cx - hx, cy - hy])
  const p1 = api.coord([cx + hx, cy + hy])
  return {
    type: 'rect',
    shape: {
      x: Math.min(p0[0]!, p1[0]!),
      y: Math.min(p0[1]!, p1[1]!),
      width: Math.abs(p1[0]! - p0[0]!),
      height: Math.abs(p1[1]! - p0[1]!)
    },
    style: { fill: api.visual('color'), stroke: 'rgba(0,0,0,0.10)', lineWidth: 1 }
  }
}

const valueSeries = computed(() =>
  props.mode === 'Field'
    ? {
        type: 'custom' as const,
        renderItem: renderTile as never,
        encode: { x: 0, y: 1, tooltip: [0, 1, 2] },
        data: tilePoints.value
      }
    : {
        type: 'scatter' as const,
        symbolSize: 13,
        data: sitePoints.value
      }
)

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const v = (params as { value: number[] }).value
      const seq = (params as { name?: string }).name
      const r = Math.hypot(v[0]!, v[1]!)
      const val = v[2] != null ? `${props.parameter}: <b>${v[2]}</b> ${props.unit}` : '측정 실패'
      return `seq ${seq} · r ${r.toFixed(1)} mm<br/>${val}`
    }
  },
  // Symmetric margins in the square body keep the wafer a true circle. Axis
  // furniture hidden — position is spatial (mm), read via tooltip.
  grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: false },
  xAxis: { type: 'value', min: -axisMax.value, max: axisMax.value, splitLine: { show: false }, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
  yAxis: { type: 'value', min: -axisMax.value, max: axisMax.value, splitLine: { show: false }, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
  visualMap: {
    // Bar hidden — the inscribed circle leaves no non-overlapping spot in the
    // square. It still maps color; the panel renders a separate DOM legend from
    // the `rangechange` event.
    show: false,
    min: valueRange.value.min, max: valueRange.value.max,
    dimension: 2, seriesIndex: 0, inRange: { color: [...SK_CHART.scale] }
  },
  series: [
    valueSeries.value,
    { type: 'line', data: waferOutline.value, showSymbol: false, silent: true,
      lineStyle: { color: SK_CHART.muted, width: 1.25, opacity: 0.55 }, tooltip: { show: false }, z: 0 },
    { type: 'scatter', symbol: 'circle', symbolSize: 24, data: outlierPoints.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.bad, borderWidth: 2 }, silent: true, z: 4 },
    { type: 'scatter', symbolSize: 13, data: failurePoints.value,
      itemStyle: { color: 'transparent' },
      label: { show: true, formatter: '✕', color: SK_CHART.bad, fontSize: 13, fontWeight: 'bold' }, z: 4 },
    { type: 'scatter', symbol: 'circle', symbolSize: 19, data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: SK_CHART.series, borderWidth: 3 }, silent: true, z: 5 }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })
</script>
