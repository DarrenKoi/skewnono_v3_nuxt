<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="text-[11px] font-semibold uppercase tracking-[0.06em] text-(--sk-ink-muted)">
        {{ label }}
      </span>
    </div>
    <div
      v-if="rows.length === 0"
      class="flex h-[28rem] items-center justify-center text-sm text-(--sk-ink-muted)"
    >
      추세 데이터가 없습니다.
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-[28rem] w-full"
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

// Pull the avg/3σ series colors from the active ECharts theme palette instead
// of hardcoding them, so the chart honors the theme picked in settings. The
// avg pane takes palette[0], the 3σ pane palette[1] — matching the indices
// ECharts would auto-assign to series[0]/series[1].
const { palette } = useEchartsTheme()
const colorAvg = computed(() => palette.value[0] ?? '#C75A3C')
const colorStd = computed(() => palette.value[1] ?? '#3F5D52')

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

// Variant B — split panels: avg on the top grid, 3σ on the bottom grid, both
// sharing a single time X axis (no dual-axis overlay). `axisPointer.link`
// fuses the two crosshairs so hovering aligns the same timestamp vertically.
const chartOption = computed<EChartsOption>(() => {
  const data = ordered.value
  return {
    grid: [
      { left: 56, right: 16, top: 28, height: '38%' },
      { left: 56, right: 16, top: '52%', bottom: 72 }
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      // One unified tooltip for both panes: look the hovered index back up in
      // `ordered` so we can show avg AND 3σ regardless of which pane is hovered.
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params]
        const idx = (list[0] as { dataIndex?: number })?.dataIndex ?? -1
        const row = data[idx]
        if (!row) return ''
        return [
          `<div style="font-weight:600;margin-bottom:2px">${row.timestamp}</div>`,
          `<div><span style="color:${colorAvg.value}">●</span> avg <b>${row[avgKey.value].toFixed(4)}</b></div>`,
          `<div><span style="color:${colorStd.value}">●</span> 3σ <b>${row[stdKey.value].toFixed(4)}</b></div>`,
          `<div style="margin-top:2px;font-size:10px;opacity:.65">클릭 → raw data</div>`
        ].join('')
      }
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }], label: { show: false } },
    xAxis: [
      {
        type: 'time',
        gridIndex: 0,
        axisLabel: { show: false },
        axisTick: { show: false }
      },
      {
        type: 'time',
        gridIndex: 1,
        axisLabel: { fontSize: 10, formatter: formatTime }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        name: 'avg',
        nameTextStyle: { fontSize: 10, color: colorAvg.value, fontWeight: 'bold' },
        axisLabel: { fontSize: 10 }
      },
      {
        type: 'value',
        gridIndex: 1,
        scale: true,
        name: '3σ',
        nameTextStyle: { fontSize: 10, color: colorStd.value, fontWeight: 'bold' },
        axisLabel: { fontSize: 10 }
        // splitLine shown (ECharts default) to match the avg pane — both
        // panes now share horizontal guide lines for the same-timestamp read.
      }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 60, end: 100, height: 16, bottom: 16 }
    ],
    series: [
      {
        name: 'avg',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: true,
        lineStyle: { color: colorAvg.value, width: 1.8 },
        itemStyle: { color: colorAvg.value },
        emphasis: { scale: 1.6 },
        data: data.map(row => ({
          name: row.timestamp,
          value: [toEpoch(row.timestamp), row[avgKey.value]],
          symbolSize: row.timestamp === props.selected ? 12 : 5
        }))
      },
      {
        name: '3σ',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: true,
        lineStyle: { color: colorStd.value, width: 1.6, type: 'dashed' },
        itemStyle: { color: colorStd.value },
        emphasis: { scale: 1.6 },
        data: data.map(row => ({
          name: row.timestamp,
          value: [toEpoch(row.timestamp), row[stdKey.value]],
          symbolSize: row.timestamp === props.selected ? 11 : 4
        }))
      }
    ]
  }
})

// Click a point in either pane → emit its timestamp (drives the raw-data /
// 360° radar selection in the parent panel).
useEchart(chartEl, chartOption, { onClick: ts => emit('select', ts) })
</script>
