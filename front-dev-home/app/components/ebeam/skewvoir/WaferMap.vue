<template>
  <div
    ref="chartEl"
    class="h-full w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { SK_CHART } from '~/utils/chartPalette'
import type { WaferGeometry } from '~/utils/waferGeometry'
import { buildWaferPoints, type WaferPoint } from '~/utils/waferPoints'
import { buildWaferAxis } from '~/utils/waferAxis'
import { formatWaferTooltip } from '~/utils/waferTooltip'
import { defaultWaferMapOptions, type WaferMapOptions } from '~/utils/waferMapOptions'

const props = withDefaults(defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  geo: WaferGeometry
  focusedSequence: number | null
  outlierSeqs: number[]
  /** 'Field' = a dot per measured point (site); 'Die' = filled die tiles. */
  mode?: 'Field' | 'Die'
  options?: WaferMapOptions
  /** Manual color-scale override; null → use the data range. */
  colorMin?: number | null
  colorMax?: number | null
}>(), {
  mode: 'Field',
  options: () => defaultWaferMapOptions(),
  colorMin: null,
  colorMax: null
})
const emit = defineEmits<{
  focus: [sequence: number]
  /** Auto (data) color range so the panel can seed its manual inputs + legend. */
  rangechange: [range: { min: number, max: number }]
}>()

const forParam = computed(() => props.rows.filter(r => r.parameter === props.parameter))

// Field = one point per measured row (each individually hoverable); Die = one
// aggregated tile per die. See utils/waferPoints.ts for why these differ.
const built = computed(() => buildWaferPoints(forParam.value, props.geo))
const activePoints = computed<WaferPoint[]>(() =>
  props.mode === 'Die' ? built.value.diePoints : built.value.fieldPoints
)

// ECharts value triples (name = sequence string, read back in tooltip/labels).
const valuePointData = computed(() =>
  activePoints.value.map(p => ({ name: String(p.seq), value: [p.x, p.y, p.value] }))
)

// seq → identity for the tooltip and MP labels.
const metaBySeq = computed(() => {
  const m = new Map<string, { field: string, mp: number, n: number }>()
  for (const p of activePoints.value) m.set(String(p.seq), { field: p.field, mp: p.mp, n: p.n })
  return m
})

// Failures (cd_value null) as ✕ marks at their physical position.
const failurePoints = computed(() =>
  built.value.failurePoints.map(f => ({ name: String(f.seq), value: [f.x, f.y] }))
)

// ◎ ring on any active point holding a sequence flagged by the overview source.
const outlierPoints = computed(() => {
  const flagged = new Set(props.outlierSeqs)
  return activePoints.value
    .filter(p => p.seqs.some(s => flagged.has(s)))
    .map(p => ({ name: String(p.seq), value: [p.x, p.y] }))
})

// Focus ring at the focused sequence's point (measured) or its ✕ (failure).
const focusPoint = computed(() => {
  const fseq = props.focusedSequence
  if (fseq == null) return []
  const hit = activePoints.value.find(p => p.seqs.includes(fseq))
  if (hit) return [{ name: String(hit.seq), value: [hit.x, hit.y] }]
  const fail = built.value.failurePoints.find(f => f.seq === fseq)
  return fail ? [{ name: String(fail.seq), value: [fail.x, fail.y] }] : []
})

const valueRange = computed(() => {
  const values = activePoints.value.map(p => p.value)
  if (values.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  return min === max ? { min: min - 0.5, max: max + 0.5 } : { min, max }
})

// Manual override (panel/modal) wins; else the data range.
const effMin = computed(() => props.colorMin ?? valueRange.value.min)
const effMax = computed(() => props.colorMax ?? valueRange.value.max)

// Publish the AUTO range (not the override) so the panel can seed manual inputs.
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

// Die mode draws each measured die as a pitch-sized rect, colored by visualMap.
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
  props.mode === 'Die'
    ? {
        type: 'custom' as const,
        renderItem: renderTile as never,
        encode: { x: 0, y: 1, tooltip: [0, 1, 2] },
        data: valuePointData.value
      }
    : {
        type: 'scatter' as const,
        symbolSize: 13,
        data: valuePointData.value,
        label: props.options.mpLabels
          ? {
              show: true,
              position: 'top' as const,
              fontSize: 9,
              color: SK_CHART.ink,
              formatter: (p: { name?: string }) => {
                const m = metaBySeq.value.get(p.name ?? '')
                return m ? String(m.mp) : ''
              }
            }
          : undefined
      }
)

// Grid on needs room for labels; equal margins on every side keep the plot rect
// square so the inscribed wafer stays a true circle (containLabel would pad
// asymmetrically and turn it into an ellipse).
const gridMargin = computed(() => (props.options.grid ? 22 : 8))

const option = computed<EChartsOption>(() => ({
  tooltip: {
    formatter: (params) => {
      const p = params as { value?: number[], name?: string }
      const seq = p.name ?? ''
      const meta = metaBySeq.value.get(seq)
      return formatWaferTooltip({
        seq,
        field: meta?.field ?? null,
        mp: meta?.mp ?? null,
        n: meta?.n ?? 1,
        param: props.parameter,
        value: p.value?.[2] ?? null,
        unit: props.unit
      })
    }
  },
  grid: {
    left: gridMargin.value, right: gridMargin.value, top: gridMargin.value, bottom: gridMargin.value,
    containLabel: false
  },
  xAxis: buildWaferAxis(props.options.grid, axisMax.value, props.geo.pitchXmm, SK_CHART.muted) as EChartsOption['xAxis'],
  yAxis: buildWaferAxis(props.options.grid, axisMax.value, props.geo.pitchYmm, SK_CHART.muted) as EChartsOption['yAxis'],
  visualMap: {
    // Bar hidden — the panel renders a separate DOM legend from `rangechange`.
    show: false,
    min: effMin.value, max: effMax.value,
    dimension: 2, seriesIndex: 0, inRange: { color: [...SK_CHART.scale] }
  },
  series: [
    valueSeries.value,
    {
      type: 'line', data: waferOutline.value, showSymbol: false, silent: true,
      lineStyle: { color: SK_CHART.muted, width: 1.25, opacity: 0.55 }, tooltip: { show: false }, z: 0,
      ...(props.options.crosshair
        ? {
            markLine: {
              silent: true, symbol: 'none',
              lineStyle: { color: SK_CHART.muted, type: 'dashed' as const, width: 1, opacity: 0.5 },
              label: { show: false },
              data: [{ xAxis: 0 }, { yAxis: 0 }]
            }
          }
        : {})
    },
    ...(props.options.notch
      ? [{
          type: 'scatter' as const, symbol: 'triangle', symbolSize: 9,
          data: [[0, -waferRadius.value]], itemStyle: { color: SK_CHART.muted },
          silent: true, z: 1, tooltip: { show: false }
        }]
      : []),
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
