<template>
  <div>
    <!-- Tool legend. This strip explains the LINE colors only — the dots carry
         the anomaly verdict, which SkAnomalyLegend already documents beside the
         chart. Two channels, two legends. -->
    <div
      v-if="legendChips.length"
      class="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1"
    >
      <span
        v-for="chip in legendChips"
        :key="chip.label"
        class="inline-flex items-center gap-1 sk-meta"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: chip.color }"
        />
        {{ chip.label }}
      </span>
    </div>
    <div
      ref="chartEl"
      class="h-80 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TrendPoint } from '~/utils/skewvoirAnalysis/timeSeries'
import type { TsAxisMode, TsBaseline } from '~/utils/skewvoirAnalysis/types'
import { placeTrendPoints, distinctEqpIds } from '~/utils/skewvoirAnalysis/timeSeries'
import { rankToolColors, toolLegendChips } from '~/utils/skewvoirAnalysis/toolColors'
import { SK_STATE } from '~/utils/chartPalette'
import { nearestPoint } from '~/utils/chartNearest'

const props = defineProps<{
  points: TrendPoint[]
  parameter: string
  unit: string
  axisMode: TsAxisMode
  baseline: TsBaseline
}>()

const emit = defineEmits<{ select: [msr: string] }>()

const sk = useChartPalette()

// `time` is the honest default; `order` is the escape hatch when measurements
// bunch; `eqp` groups the set into one column per tool. Under `order`/`eqp`
// the x value is an index, so spacing is uniform. A point with an unparseable
// ts has no position on a time axis, so the time branch drops it —
// placeTrendPoints owns that rule and the panel meta counts what it dropped
// with the same function.
const placed = computed(() => placeTrendPoints(props.points, props.axisMode))

// Tool identity colors + legend chips, shared with SequenceTrend via
// utils/skewvoirAnalysis/toolColors so one tool never wears two colors.
//
// Ranked over `placed`, NOT props.points: a hidden measurement must not spend
// an identity color, or a tool that IS drawn gets pushed into 기타 by points
// nobody can see — and a tool whose measurements were all hidden would get a
// legend chip with no line under it.
const toolColor = computed(() => rankToolColors(placed.value.map(({ p }) => p.eqpId)))
const legendChips = computed(() => toolLegendChips(toolColor.value))

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
const sevKey = (p: TrendPoint): string =>
  !p.verdict ? 'normal' : p.verdict.status === 'insufficient' ? 'insufficient' : p.verdict.severity

// Strictly ordered: abnormal > watch > insufficient > normal, so size alone
// still ranks severity. The floor is 7, not 6 — an item-triggered tooltip makes
// the symbol the ONLY hover target, and a 6px dot is a hard thing to hit on a
// dense set. `emphasis.scale` on the series grows whichever one is hovered.
const symbolFor = (key: string): number =>
  key === 'abnormal' ? 10 : key === 'watch' ? 9 : key === 'insufficient' ? 8 : 7

interface TrendDatum {
  value: [number, number]
  itemStyle: { color: string }
  symbolSize: number
  /** The measurement this symbol stands for. Carried on the datum because
   *  `dataIndex` now indexes ONE tool's array, so neither the tooltip nor the
   *  click handler can look the measurement up in `props.points`. */
  point: TrendPoint
}

// One series per tool. The LINE carries tool identity; each POINT keeps the
// severity color the sevHex table produces, so a red dot still means "this
// measurement was judged abnormal", never "this is tool 3".
//
// Under the `eqp` axis a tool's points all share one x, so the connecting line
// would be a meaningless vertical stroke — the line is hidden there and the
// symbols alone carry the column.
//
// This array is the ONLY grouping pass: the tooltip reads `point` off the datum
// and the click handler indexes back into this same array, so there is no
// second structure that could drift out of step with the series order.
const toolSeries = computed(() => {
  const byTool = new Map<string, TrendDatum[]>()
  for (const { p, x } of placed.value) {
    const key = sevKey(p)
    const datum: TrendDatum = {
      value: [x, p.value],
      itemStyle: { color: sevHex.value[key]! },
      symbolSize: symbolFor(key),
      point: p
    }
    const list = byTool.get(p.eqpId)
    if (list) list.push(datum)
    else byTool.set(p.eqpId, [datum])
  }
  return [...byTool].map(([eqpId, data]) => ({
    name: eqpId,
    type: 'line' as const,
    data,
    smooth: false,
    showSymbol: true,
    lineStyle: {
      width: 2,
      opacity: props.axisMode === 'eqp' ? 0 : 1,
      color: toolColor.value.get(eqpId) ?? sk.value.series
    },
    itemStyle: { color: toolColor.value.get(eqpId) ?? sk.value.series },
    // Grow the hovered symbol so a small dot is findable and stays under the
    // cursor once found. Scale only — no `focus`, which would dim the other
    // tools and defeat the cross-tool comparison this chart exists for.
    emphasis: { scale: 1.8 },
    z: 3
  }))
})

// min/max band rendered as two stacked lines: a transparent floor at bandLo,
// then a translucent area of height (bandHi - bandLo) on top of it. The band
// spans the whole set, not one tool, so it stays two global silent series
// behind everything. bandLo/bandHi are already baseline-shifted.
//
// Not drawn under the `eqp` axis: several measurements share each x there, so
// a per-point area would zigzag up and down one column and read as noise.
const floorData = computed(() => placed.value.map(({ p, x }) => [x, p.bandLo]))
const bandData = computed(() =>
  placed.value.map(({ p, x }) => [x, Number((p.bandHi - p.bandLo).toFixed(3))])
)

// How many band series sit ahead of the per-tool ones — a series index has to
// be shifted by this much before it indexes toolSeries.
const bandCount = computed(() => (props.axisMode === 'eqp' ? 0 : 2))

// The crosshair is an AXIS component, not a tooltip feature, so it survives the
// item-triggered tooltip: the reader keeps a vertical reference for lining a
// point up against the band and against the other tools, which is exactly what
// leaving `trigger: 'axis'` cost. `snap` puts it on measurements rather than on
// arbitrary pixels. Color comes from the theme's axisPointer styling.
const AXIS_POINTER = { show: true, type: 'line' as const, snap: true, label: { show: false } }

const yName = computed(() => {
  const base = props.unit ? `${props.parameter} (${props.unit})` : props.parameter
  return props.baseline === 'resid'
    ? `Δ vs 세트 기준${props.unit ? ` (${props.unit})` : ''}`
    : base
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    // `item`, not `axis`: with one series per tool an axis tooltip would list
    // every tool's nearest datum as if they shared an x. The hovered symbol
    // carries its own TrendPoint, so what is shown is what is under the cursor.
    trigger: 'item',
    formatter: (params) => {
      const hit = Array.isArray(params) ? params[0] : params
      // The band series carry plain [x, y] arrays and are silent, so a miss
      // here means "not a trend symbol" and renders nothing.
      const p = (hit as { data?: { point?: TrendPoint } } | undefined)?.data?.point
      if (!p) return ''
      const lines = [
        p.label,
        `eqp: ${p.eqpId}`,
        `mean: <b>${p.mean}</b> ${props.unit}`
      ]
      // In residual mode the plotted y is NOT the mean, so name the shift
      // rather than letting the reader assume the dot sits at `mean`.
      if (props.baseline === 'resid') {
        lines.push(`Δ vs 세트 기준: <b>${Number(p.value.toFixed(3))}</b> ${props.unit}`)
      }
      lines.push(`min/max: ${p.min} / ${p.max}`, `std: ${p.std}`)
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
  // top 28, not 20: `containLabel` reserves room for axis LABELS but not for the
  // axis NAME, which yAxis draws above the grid at the default nameGap of 15.
  // At 20 the name is half-clipped by the canvas edge — verified in the browser,
  // where “Δ vs 세트 기준” (the whole point of residual mode) was unreadable.
  grid: { left: 48, right: 16, top: 28, bottom: 64, containLabel: true },
  xAxis: props.axisMode === 'time'
    ? { type: 'time' as const, axisLabel: { fontSize: 10, hideOverlap: true }, axisPointer: AXIS_POINTER }
    : props.axisMode === 'eqp'
      ? {
          // One column per tool; labels are eqp ids, few enough to stay flat.
          // The data MUST be distinctEqpIds — the same list placeTrendPoints
          // indexed into — or points land under the wrong tool.
          type: 'category' as const,
          data: distinctEqpIds(props.points),
          axisLabel: { fontSize: 10, hideOverlap: true },
          boundaryGap: true,
          axisPointer: AXIS_POINTER
        }
      : {
          type: 'category' as const,
          data: props.points.map(p => p.label),
          axisLabel: { fontSize: 10, rotate: 35, hideOverlap: true },
          boundaryGap: true,
          axisPointer: AXIS_POINTER
        },
  yAxis: {
    type: 'value',
    scale: true,
    name: yName.value,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 },
    splitLine: { show: true }
  },
  series: [
    ...(bandCount.value === 0
      ? []
      : [
          {
            name: 'min',
            type: 'line' as const,
            stack: 'band',
            data: floorData.value,
            lineStyle: { opacity: 0 },
            symbol: 'none',
            silent: true,
            z: 1
          },
          {
            name: 'range',
            type: 'line' as const,
            stack: 'band',
            // REQUIRED, not decoration. ECharts' default stackStrategy is 'samesign'
            // (processor/dataStack.js), which stacks a value onto its predecessor
            // only when both share a sign. In residual mode bandLo is negative for
            // every measurement below the 세트 기준 — about half of them, since the
            // baseline is the median — so the floor would be skipped, stackedOver
            // would stay NaN, and the band would draw from the axis origin, leaving
            // the mean dot outside its own band. 'all' stacks unconditionally.
            stackStrategy: 'all' as const,
            data: bandData.value,
            lineStyle: { opacity: 0 },
            areaStyle: { color: sk.value.series, opacity: 0.12 },
            symbol: 'none',
            silent: true,
            z: 1
          }
        ]),
    ...toolSeries.value
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
// Every plotted measurement, flattened out of the per-tool series so a click
// can be resolved against all of them at once. Several tools overlap in this
// chart, so the pick has to weigh both axes — the reader aims at a dot, not at
// a moment, and two tools an hour apart are told apart by their value.
const clickable = computed(() =>
  toolSeries.value.flatMap(series =>
    series.data.map(datum => ({ x: datum.value[0], y: datum.value[1], item: datum.point.msr }))
  )
)

useEchart(chartEl, option, {
  onDataIndex: (dataIndex: number, seriesIndex: number) => {
    // The band series are `silent: true` so they should never fire, but an
    // out-of-range index resolves to undefined and emits nothing rather than
    // selecting the wrong measurement.
    const msr = toolSeries.value[seriesIndex - bandCount.value]?.data[dataIndex]?.point.msr
    if (msr) emit('select', msr)
  },
  // A near-miss on a 7px dot used to do nothing. Now it selects the measurement
  // nearest the pointer — but only within the pick radius, since this chart has
  // legitimately empty regions (a tool that stopped reporting) where selecting
  // something far away would be a guess, not a correction.
  onGridClick: (detail) => {
    const msr = nearestPoint(clickable.value, detail)
    if (msr) emit('select', msr)
  }
})
</script>
