<template>
  <div
    ref="chartEl"
    class="h-72 w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileResponse } from '~/composables/useMsrFileApi'

const props = defineProps<{
  file: MsrFileResponse
  // FDC param name to trace across sequences (key of dynamic_fdc inner dict).
  param: string
}>()

const summary = computed(() =>
  props.file.fdc_params.find(p => p.name === props.param) ?? null
)

// dynamic_fdc is keyed by sequence string; sort numerically for the x-axis.
const series = computed(() => {
  const entries = Object.entries(props.file.dynamic_fdc)
    .map(([seq, params]) => [Number(seq), params[props.param]] as const)
    .filter(([, v]) => v != null)
    .sort((a, b) => a[0] - b[0])
  return entries.map(([seq, v]) => [seq, v as number])
})

const unit = computed(() => summary.value?.unit ?? '')

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const p = (Array.isArray(params) ? params[0] : params) as { value: number[] }
      return `seq ${p.value[0]}<br/>${props.param}: <b>${p.value[1]}</b> ${unit.value}`
    }
  },
  grid: { left: 44, right: 16, top: 24, bottom: 32, containLabel: true },
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
    name: unit.value ? `${props.param} (${unit.value})` : props.param,
    axisLabel: { fontSize: 10 },
    splitLine: { show: false },
    nameTextStyle: { fontSize: 10 }
  },
  series: [{
    type: 'line',
    data: series.value,
    smooth: false,
    showSymbol: true,
    symbolSize: 4,
    lineStyle: { width: 1.5, color: '#7c3aed' },
    itemStyle: { color: '#7c3aed' },
    // Nominal reference so the intra-run drift away from baseline is obvious.
    ...(summary.value
      ? {
          markLine: {
            silent: true,
            symbol: 'none',
            label: { fontSize: 9, formatter: 'nominal' },
            lineStyle: { color: '#94a3b8', type: 'dashed' },
            data: [{ yAxis: summary.value.nominal }]
          }
        }
      : {})
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
