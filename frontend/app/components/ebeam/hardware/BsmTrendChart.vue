<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="sk-title">
        {{ label }}
      </span>
    </div>
    <div
      v-if="points.length === 0"
      class="flex h-72 items-center justify-center sk-body"
    >
      추세 데이터가 없습니다.
    </div>
    <!-- The click listener only serves the tooltip's inspect button, which
         ECharts renders inside this element; canvas clicks fall through. -->
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
      @click="onTooltipClick"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { stableYRange, tightYRange, type StableYRangeOptions } from '~/utils/chartRange'
import { BM_PM_LEGEND_GRID_TOP, bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'
import { trendSymbolSize } from '~/utils/chartSymbolSize'
import { nearestPoint } from '~/utils/chartNearest'
import { inspectButtonHtml, inspectKeyOf, inspectTooltipBase } from '~/utils/chartInspectTooltip'

const props = defineProps<{
  label: string
  points: { ts: string, key: string, value: number }[]
  selected: string
  // MDC corrections drift ±0.55% around 1.0 — the drift IS the signal, so
  // 'tight' skips stableYRange's magnitude-relative floor (which would
  // flatten the series) and lets the axis hug the data.
  yMode?: 'stable' | 'tight'
  // Tuning for 'stable' mode (e.g. a smaller minSpanRatio hugs the data more
  // closely). Omitted → stableYRange defaults; ignored in 'tight' mode.
  yOptions?: StableYRangeOptions
  // BM/PM maintenance timestamps drawn as vertical markLines (empty → none).
  events?: BmPmEvent[]
  // Optional comparison tools drawn as thin extra lines (empty/omitted → the
  // chart stays single-series, so BsmPanel/SharpnessPanel are unaffected).
  overlays?: { name: string, points: { ts: string, value: number }[], color?: string }[]
  // Adds a button to the tooltip that emits `inspect` with the hovered point's
  // key, so the reader decides whether to open a detail (Sharpness → recipes
  // measured around that time). Off → the plain tooltip.
  inspectLabel?: string
  // Axis ticks show MM/DD only, one per day at most — for slow-moving series
  // (MDC corrections change a few times a week) where hh:mm is noise.
  dateOnly?: boolean
  // Draw as a step line: the value holds until the next point, then jumps.
  // For snapshot series that change in discrete adjustments (MDC), where a
  // slope between two snapshots would suggest a gradual drift that never was.
  step?: boolean
}>()

const emit = defineEmits<{ select: [key: string], inspect: [key: string] }>()

const chartEl = ref<HTMLDivElement | null>(null)
const { palette } = useEchartsTheme()
const color = computed(() => palette.value[0] ?? '#C75A3C')
const colorMode = useColorMode()

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()
const formatTime = (value: number | string) => {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}/${dd} ${hh}:${mi}`
}
// dateOnly labels midnight ticks only. Under a day's span ECharts ignores
// minInterval and ticks hourly (zoomed in, or at the extent's ragged ends);
// printing MM/DD on those would repeat the same date, so they stay blank.
const formatAxisTime = (value: number | string) => {
  const full = formatTime(value)
  if (!props.dateOnly) return full
  return full.endsWith(' 00:00') ? full.slice(0, 5) : ''
}

// Points arrive ascending (oldest first) from the panel.
const overlays = computed(() => props.overlays ?? [])

// Dots are sized from the room actually available — see chartSymbolSize.ts for
// why spacing rather than point count decides it. The host has to be measured
// because the same chart renders full-width in SharpnessPanel and half-width in
// BsmPanel's side-by-side panes.
const hostWidth = useElementWidth(chartEl)

// Sized against the grid's inner width, so the margins below have to be kept in
// step with the `grid` option.
const symbolSize = computed(() =>
  trendSymbolSize(hostWidth.value - 72, props.points.length) // grid left 56 + right 16
)
const hasOverlays = computed(() => overlays.value.length > 0)

// The y-axis must span the overlays too, or comparison tools drawn at a
// different correction level would clip out of view.
const yValues = computed(() => [
  ...props.points.map(p => p.value),
  ...overlays.value.flatMap(o => o.points.map(p => p.value))
])

const plainTooltip = {
  trigger: 'axis' as const,
  axisPointer: { type: 'line' as const },
  valueFormatter: (v: unknown) => (typeof v === 'number' ? v.toFixed(4) : String(v))
}

// An axis tooltip snaps on x only, so it opens straight below the cursor:
// moving down into it keeps the same point (pinned in chartInspectTooltip).
const inspectBase = inspectTooltipBase()
const inspectTooltip = computed(() => ({
  ...plainTooltip,
  ...inspectBase,
  formatter: (params: unknown) => {
    const items = (Array.isArray(params) ? params : [params]) as { seriesIndex: number, name: string, marker: string, seriesName: string, value: [number, number] }[]
    const main = items.find(item => item.seriesIndex === 0)
    const lines = items.map(item =>
      `${item.marker}${escapeHtml(item.seriesName && hasOverlays.value ? `${item.seriesName} ` : '')}<b>${item.value[1].toFixed(4)}</b>`)
    const button = main ? inspectButtonHtml(main.name, props.inspectLabel!) : ''
    return `${formatTime(items[0]?.value[0] ?? '')}<br/>${lines.join('<br/>')}<br/>${button}`
  }
}))

const onTooltipClick = (event: MouseEvent) => {
  const key = inspectKeyOf(event)
  if (key) emit('inspect', key)
}

const chartOption = computed<EChartsOption>(() => ({
  // Only overlays bring a legend; without one the BM/PM labels fit in top 16.
  grid: { left: 56, right: 16, top: hasOverlays.value ? BM_PM_LEGEND_GRID_TOP : 16, bottom: 56 },
  tooltip: props.inspectLabel ? inspectTooltip.value : plainTooltip,
  ...(hasOverlays.value ? { legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } } } : {}),
  xAxis: {
    type: 'time',
    ...(props.dateOnly ? { minInterval: 24 * 3600 * 1000 } : {}),
    axisLabel: { fontSize: 10, formatter: formatAxisTime }
  },
  yAxis: {
    type: 'value',
    ...(props.yMode === 'tight'
      ? (tightYRange(yValues.value) ?? { scale: true })
      : (stableYRange(yValues.value, props.yOptions) ?? { scale: true })),
    axisLabel: { fontSize: 10 },
    // Flat parameters + a tight y-range packs horizontal splitLines right
    // behind the series, where they read as data. Vertical (time) lines stay.
    splitLine: { show: false }
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 16, bottom: 12 }
  ],
  series: [
    {
      // Named only when overlays share the chart, so a solo chart keeps no legend.
      ...(hasOverlays.value ? { name: props.label } : {}),
      type: 'line',
      step: props.step ? 'end' : false,
      showSymbol: true,
      lineStyle: { color: color.value, width: 1.8 },
      itemStyle: { color: color.value },
      emphasis: { scale: 1.6 },
      markLine: bmPmMarkLine(props.events ?? [], { dark: colorMode.value === 'dark' }),
      data: props.points.map(p => ({
        name: p.key,
        value: [toEpoch(p.ts), p.value],
        symbolSize: p.key === props.selected ? symbolSize.value + 5 : symbolSize.value
      }))
    },
    ...overlays.value.map(o => ({
      name: o.name,
      type: 'line' as const,
      step: props.step ? 'end' as const : false as const,
      showSymbol: false,
      smooth: false,
      lineStyle: { color: o.color ?? '#94a3b8', width: 1, opacity: 0.9 },
      itemStyle: { color: o.color ?? '#94a3b8' },
      data: o.points.map(p => [toEpoch(p.ts), p.value] as [number, number])
    }))
  ]
}))

// Picking the measurement nearest the clicked time, rather than requiring a hit
// on the symbol itself. `onClick` alone means the target is only as wide as the
// dot, which readers were missing; this makes the whole plot area the target,
// so a near-miss still selects what the reader was aiming at. Both fire — a
// direct hit goes through onClick and never reaches here.
//
// This is a trend read left-to-right — one measurement per timestamp — so the
// click means "that moment" and how high the cursor sat carries no intent.
const candidates = computed(() =>
  props.points.map(p => ({ x: toEpoch(p.ts), y: 0, item: p.key }))
)

useEchart(chartEl, chartOption, {
  onClick: ts => emit('select', ts),
  onGridClick: (detail) => {
    // No radius cap: anywhere inside the plot is a deliberate pick of a moment.
    const key = nearestPoint(candidates.value, detail, { xOnly: true, maxDistancePx: Infinity })
    if (key) emit('select', key)
  }
})
</script>
