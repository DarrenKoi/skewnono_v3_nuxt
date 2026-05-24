<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="text-[11px] font-semibold uppercase tracking-[0.06em] text-(--sk-ink-muted)">
        {{ label }}
      </span>
    </div>
    <div
      v-if="rows.length === 0"
      class="flex h-72 items-center justify-center text-sm text-(--sk-ink-muted)"
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
import type { BsmMetric, BsmSummaryRow } from '~/composables/useHardwareApi'

const props = defineProps<{
  metric: BsmMetric
  label: string
  rows: BsmSummaryRow[]
  selected: string
}>()

const emit = defineEmits<{ select: [timestamp: string] }>()

const chartEl = ref<HTMLDivElement | null>(null)

// "2026-05-24 22:30" → epoch ms (normalize the space to 'T' so every browser
// parses it the same way).
const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const formatTime = (value: number | string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${month}/${day} ${hours}:${minutes}`
}

const avgKey = computed(() => `${props.metric}_avg` as const)
const stdKey = computed(() => `${props.metric}_3std` as const)

// Rows arrive timestamp-desc; charts read left-to-right (oldest first).
const ordered = computed(() => [...props.rows].reverse())

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 48, right: 48, top: 36, bottom: 64, containLabel: true },
  tooltip: {
    trigger: 'axis',
    valueFormatter: value => (typeof value === 'number' ? value.toFixed(3) : String(value))
  },
  legend: { top: 0, right: 8, textStyle: { fontSize: 11 } },
  xAxis: {
    type: 'time',
    axisLabel: { fontSize: 10, formatter: formatTime }
  },
  yAxis: [
    { type: 'value', name: 'avg', scale: true, axisLabel: { fontSize: 10 } },
    { type: 'value', name: '3σ', scale: true, axisLabel: { fontSize: 10 }, splitLine: { show: false } }
  ],
  dataZoom: [
    { type: 'inside', start: 60, end: 100 },
    { type: 'slider', start: 60, end: 100, height: 20, bottom: 20 }
  ],
  series: [
    {
      name: 'avg',
      type: 'line',
      yAxisIndex: 0,
      showSymbol: true,
      data: ordered.value.map(row => ({
        name: row.timestamp,
        value: [toEpoch(row.timestamp), row[avgKey.value]],
        symbolSize: row.timestamp === props.selected ? 13 : 6
      }))
    },
    {
      name: '3σ',
      type: 'line',
      yAxisIndex: 1,
      showSymbol: true,
      lineStyle: { type: 'dashed' },
      data: ordered.value.map(row => ({
        name: row.timestamp,
        value: [toEpoch(row.timestamp), row[stdKey.value]],
        symbolSize: row.timestamp === props.selected ? 11 : 5
      }))
    }
  ]
}))

useEchart(chartEl, chartOption, { onClick: ts => emit('select', ts) })
</script>
