<template>
  <div class="flex flex-col">
    <div class="mb-1 flex items-center gap-2 px-1">
      <span class="text-[11px] font-semibold uppercase tracking-[0.06em] text-(--sk-ink-muted)">
        {{ label }}
      </span>
    </div>
    <div
      v-if="points.length === 0"
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
import { stableYRange } from '~/utils/chartRange'

const props = defineProps<{
  label: string
  points: { ts: string, key: string, value: number }[]
  selected: string
}>()

const emit = defineEmits<{ select: [key: string] }>()

const chartEl = ref<HTMLDivElement | null>(null)
const { palette } = useEchartsTheme()
const color = computed(() => palette.value[0] ?? '#C75A3C')

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
const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 16, top: 16, bottom: 56 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'line' },
    valueFormatter: v => (typeof v === 'number' ? v.toFixed(4) : String(v))
  },
  xAxis: { type: 'time', axisLabel: { fontSize: 10, formatter: formatTime } },
  yAxis: {
    type: 'value',
    ...(stableYRange(props.points.map(p => p.value)) ?? { scale: true }),
    axisLabel: { fontSize: 10 }
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 16, bottom: 12 }
  ],
  series: [
    {
      type: 'line',
      showSymbol: true,
      lineStyle: { color: color.value, width: 1.8 },
      itemStyle: { color: color.value },
      emphasis: { scale: 1.6 },
      data: props.points.map(p => ({
        name: p.key,
        value: [toEpoch(p.ts), p.value],
        symbolSize: p.key === props.selected ? 12 : 5
      }))
    }
  ]
}))

useEchart(chartEl, chartOption, { onClick: ts => emit('select', ts) })
</script>
