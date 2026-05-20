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

// cd_value across measurement order within the MSR — surfaces intra-wafer drift.
const series = computed(() =>
  props.rows
    .filter(r => r.parameter === props.parameter)
    .sort((a, b) => a.sequence - b.sequence)
    .map(r => [r.sequence, r.cd_value])
)

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const p = (Array.isArray(params) ? params[0] : params) as { value: number[] }
      return `seq ${p.value[0]}<br/>${props.parameter}: <b>${p.value[1]}</b> ${props.unit}`
    }
  },
  grid: { left: 40, right: 16, top: 24, bottom: 32, containLabel: true },
  xAxis: {
    type: 'value',
    name: 'sequence',
    nameLocation: 'middle',
    nameGap: 24,
    axisLabel: { fontSize: 10 },
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit,
    axisLabel: { fontSize: 10 },
    splitLine: { show: false },
    nameTextStyle: { fontSize: 10 }
  },
  series: [{
    type: 'line',
    data: series.value,
    smooth: false,
    showSymbol: true,
    symbolSize: 5,
    lineStyle: { width: 1.5 }
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
