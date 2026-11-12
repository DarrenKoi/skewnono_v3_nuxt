<template>
  <div
    ref="el"
    class="w-full"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { formatSecondsAsDuration, formatSecondsCompact } from '~/composables/useRecipeTatApi'
import type { RecipeUsageDailyPoint } from '~/composables/useRecipeUsageApi'
import { SK_STATE } from '~/utils/chartPalette'
import { CHART_AXIS_LABEL, CHART_LEGEND_LABEL } from '~/utils/chartType'

// Daily runs (stacked: ended normally + fail) with total measurement time on a
// second axis. The caller sizes it with a height class.
const props = defineProps<{
  points: readonly RecipeUsageDailyPoint[]
  exportName: string
}>()

const sk = useChartPalette()
const el = ref<HTMLDivElement | null>(null)

const tooltip = (params: unknown) => {
  const first = (Array.isArray(params) ? params[0] : params) as { dataIndex?: number } | undefined
  const point = props.points[first?.dataIndex ?? 0]
  if (!point) return ''
  return [
    `<b>${point.date}</b>`,
    `작업 수: ${point.runs.toLocaleString()}`,
    `Fail: ${point.fail_runs.toLocaleString()}`,
    `Wafer: ${point.wafers.toLocaleString()}`,
    `측정 시간: ${formatSecondsAsDuration(point.meas_min * 60)}`
  ].join('<br/>')
}

const option = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: tooltip },
  legend: { top: 0, textStyle: CHART_LEGEND_LABEL },
  grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
  xAxis: {
    type: 'category',
    data: props.points.map(point => point.date.slice(5)),
    axisLabel: CHART_AXIS_LABEL
  },
  yAxis: [
    { type: 'value', minInterval: 1, axisLabel: CHART_AXIS_LABEL },
    {
      type: 'value',
      splitLine: { show: false },
      axisLabel: { ...CHART_AXIS_LABEL, formatter: (minutes: number) => formatSecondsCompact(minutes * 60) }
    }
  ],
  series: [
    {
      name: '정상 종료',
      type: 'bar',
      stack: 'runs',
      barMaxWidth: 22,
      itemStyle: { color: sk.value.series },
      data: props.points.map(point => point.runs - point.fail_runs)
    },
    {
      name: 'Fail',
      type: 'bar',
      stack: 'runs',
      barMaxWidth: 22,
      itemStyle: { color: SK_STATE.bad },
      data: props.points.map(point => point.fail_runs)
    },
    {
      name: '측정 시간',
      type: 'line',
      yAxisIndex: 1,
      showSymbol: props.points.length <= 31,
      itemStyle: { color: sk.value.brand },
      lineStyle: { color: sk.value.brand },
      data: props.points.map(point => point.meas_min)
    }
  ]
}))

useEchart(el, option, { exportName: props.exportName })
</script>
