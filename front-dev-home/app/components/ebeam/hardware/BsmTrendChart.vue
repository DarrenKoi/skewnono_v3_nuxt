<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="sk-eyebrow">
        {{ label }}
      </span>
    </div>
    <div
      v-if="points.length === 0"
      class="flex h-72 items-center justify-center sk-body"
    >
      추세 데이터가 없습니다.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { stableYRange, tightYRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  label: string
  points: { ts: string, key: string, value: number }[]
  selected: string
  // MDC corrections drift ±0.55% around 1.0 — the drift IS the signal, so
  // 'tight' skips stableYRange's magnitude-relative floor (which would
  // flatten the series) and lets the axis hug the data.
  yMode?: 'stable' | 'tight'
  // BM/PM maintenance timestamps drawn as vertical markLines (empty → none).
  events?: BmPmEvent[]
  // Optional comparison tools drawn as thin extra lines (empty/omitted → the
  // chart stays single-series, so BsmPanel/SharpnessPanel are unaffected).
  overlays?: { name: string, points: { ts: string, value: number }[], color?: string }[]
}>()

const emit = defineEmits<{ select: [key: string] }>()

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

// Points arrive ascending (oldest first) from the panel.
const overlays = computed(() => props.overlays ?? [])
const hasOverlays = computed(() => overlays.value.length > 0)

// The y-axis must span the overlays too, or comparison tools drawn at a
// different correction level would clip out of view.
const yValues = computed(() => [
  ...props.points.map(p => p.value),
  ...overlays.value.flatMap(o => o.points.map(p => p.value))
])

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 16, top: hasOverlays.value ? 28 : 16, bottom: 56 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'line' },
    valueFormatter: v => (typeof v === 'number' ? v.toFixed(4) : String(v))
  },
  ...(hasOverlays.value ? { legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } } } : {}),
  xAxis: { type: 'time', axisLabel: { fontSize: 10, formatter: formatTime } },
  yAxis: {
    type: 'value',
    ...(props.yMode === 'tight'
      ? (tightYRange(yValues.value) ?? { scale: true })
      : (stableYRange(yValues.value) ?? { scale: true })),
    axisLabel: { fontSize: 10 }
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
      showSymbol: true,
      lineStyle: { color: color.value, width: 1.8 },
      itemStyle: { color: color.value },
      emphasis: { scale: 1.6 },
      markLine: bmPmMarkLine(props.events ?? [], { dark: colorMode.value === 'dark' }),
      data: props.points.map(p => ({
        name: p.key,
        value: [toEpoch(p.ts), p.value],
        symbolSize: p.key === props.selected ? 12 : 5
      }))
    },
    ...overlays.value.map(o => ({
      name: o.name,
      type: 'line' as const,
      showSymbol: false,
      smooth: false,
      lineStyle: { color: o.color ?? '#94a3b8', width: 1, opacity: 0.9 },
      itemStyle: { color: o.color ?? '#94a3b8' },
      data: o.points.map(p => [toEpoch(p.ts), p.value] as [number, number])
    }))
  ]
}))

useEchart(chartEl, chartOption, { onClick: ts => emit('select', ts) })
</script>
