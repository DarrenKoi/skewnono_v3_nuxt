<template>
  <div
    ref="chartEl"
    role="img"
    tabindex="0"
    class="h-56 w-full"
    :aria-label="ariaLabel"
  />
  <span class="sr-only">{{ ariaLabel }}</span>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { alignToSequences, type SeqPoint } from '~/utils/skewvoirAnalysis/sequence'
import { nearestIndex } from '~/utils/chartNearest'

// A single SHARED-CURSOR sequence pane. Repurposed from the old FDC-only trend
// into a generic measurement-order line so the CD pane and every dynamic-FDC
// pane in the sequence workbench share one implementation (and one cursor).
//
// X axis is CATEGORY (the shared sequence list rendered as labels) so a click
// reports the sequence value directly through useEchart's name-based onClick —
// every stacked pane indexes the identical axis, keeping the cursor aligned.
// Different units live in SEPARATE panes; this component never combines two.
const props = defineProps<{
  // Points for THIS pane's series (sequence + value + measured).
  points: SeqPoint[]
  // The shared sequence axis (same array for every pane), as categories.
  sequences: number[]
  // Series label + its own unit (never merged with another pane's unit).
  name: string
  unit: string
  // Optional nominal reference line (dynamic-FDC panes have one; CD does not).
  nominal?: number | null
  // The shared cursor — the focused sequence, or null.
  focused?: number | null
  // Line/point colour for this pane.
  color?: string
}>()

const emit = defineEmits<{ select: [sequence: number] }>()

const categories = computed(() => props.sequences.map(s => String(s)))

// Align this pane's points onto the shared axis; missing sequences → null gap.
const data = computed(() => alignToSequences(props.points, props.sequences))

const sk = useChartPalette()
const color = computed(() => props.color ?? sk.value.series)

// Screen-reader text alternative: the pane's own N/start/end, mirroring the
// numbers the panel's meta line already shows sighted users.
const ariaLabel = computed(() => {
  const vals = data.value.filter((v): v is number => v != null)
  if (!vals.length) return `${props.name} 측정 순서 추이: 데이터 없음`
  const start = vals[0]!
  const end = vals[vals.length - 1]!
  return `${props.name} 측정 순서 추이: ${vals.length}개 지점, 시작 ${start.toFixed(2)}${props.unit} → 종료 ${end.toFixed(2)}${props.unit}`
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const p = (Array.isArray(params) ? params[0] : params) as unknown as { axisValue: string, value: number | null }
      const v = p.value == null ? '—' : `<b>${p.value}</b> ${props.unit}`
      return `측정 순서 ${p.axisValue}<br/>${props.name}: ${v}`
    }
  },
  grid: { left: 46, right: 16, top: 20, bottom: 30, containLabel: true },
  xAxis: {
    type: 'category',
    data: categories.value,
    name: '측정 순서',
    nameLocation: 'middle',
    nameGap: 22,
    axisLabel: { fontSize: 10 },
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit ? `${props.name} (${props.unit})` : props.name,
    axisLabel: { fontSize: 10 },
    splitLine: { show: false },
    nameTextStyle: { fontSize: 10 }
  },
  series: [{
    type: 'line',
    data: data.value,
    connectNulls: false,
    smooth: false,
    showSymbol: true,
    symbolSize: 5,
    lineStyle: { width: 1.5, color: color.value },
    itemStyle: { color: color.value },
    markLine: {
      silent: true,
      symbol: 'none',
      data: [
        // The shared cursor (vertical), when a sequence is focused.
        ...(props.focused != null
          ? [{ xAxis: String(props.focused), lineStyle: { color: color.value, width: 1.5, type: 'solid' as const }, label: { show: false } }]
          : []),
        // Nominal baseline (dynamic-FDC panes only), when provided.
        ...(props.nominal != null && Number.isFinite(props.nominal)
          ? [{ yAxis: props.nominal, lineStyle: { color: sk.value.muted, type: 'dashed' as const }, label: { fontSize: 9, formatter: 'nominal' } }]
          : [])
      ]
    }
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, {
  onClick: (name) => {
    const seq = Number(name)
    if (Number.isFinite(seq)) emit('select', seq)
  },
  // A 5px dot is a ~10px target, and the panes stack several to a screen — too
  // small to hit reliably. Clicking anywhere in the pane moves the shared
  // cursor to the sequence under the pointer instead, which is also what the
  // vertical cursor line already implies is clickable.
  onGridClick: ({ x }) => {
    const index = nearestIndex(x, props.sequences.length)
    const seq = index == null ? null : props.sequences[index]
    if (seq != null) emit('select', seq)
  }
})
</script>
