<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const props = defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
}>()

const BIN_COUNT = 12

const values = computed(() =>
  props.rows.filter(r => r.parameter === props.parameter).map(r => r.cd_value)
)

const histogram = computed(() => {
  const vals = values.value
  if (vals.length === 0) return { labels: [] as string[], counts: [] as number[], mean: 0 }

  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const width = span / BIN_COUNT
  const counts = new Array(BIN_COUNT).fill(0)

  for (const v of vals) {
    const idx = Math.min(BIN_COUNT - 1, Math.floor((v - min) / width))
    counts[idx] += 1
  }

  const labels = counts.map((_, i) => (min + width * (i + 0.5)).toFixed(1))
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length
  return { labels, counts, mean }
})

const option = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: histogram.value.labels,
    axisLabel: { fontSize: 10 },
    name: props.unit ? `${props.parameter} (${props.unit})` : props.parameter,
    nameLocation: 'middle',
    nameGap: 26,
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 10 },
    splitLine: { show: false },
    name: 'count',
    nameTextStyle: { fontSize: 10 }
  },
  series: [{
    type: 'bar',
    data: histogram.value.counts,
    barWidth: '90%',
    itemStyle: { borderRadius: [2, 2, 0, 0] },
    markLine: {
      symbol: 'none',
      lineStyle: { color: '#ef4444', type: 'dashed' },
      label: { formatter: `mean ${histogram.value.mean.toFixed(2)}`, fontSize: 10 },
      data: [{ xAxis: histogram.value.mean ? histogram.value.labels.findIndex(l => Number(l) >= histogram.value.mean) : 0 }]
    }
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
