<template>
  <div
    ref="chartEl"
    class="h-56 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { SeqPoint } from '~/utils/skewvoirAnalysis/sequence'

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
const data = computed(() => {
  const bySeq = new Map(props.points.map(p => [p.sequence, p.measured ? p.value : null]))
  return props.sequences.map(s => bySeq.get(s) ?? null)
})

const color = computed(() => props.color ?? '#2563eb')

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
          ? [{ yAxis: props.nominal, lineStyle: { color: '#94a3b8', type: 'dashed' as const }, label: { fontSize: 9, formatter: 'nominal' } }]
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
  }
})
</script>
