<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      장비별 skew 트렌드 · BM/PM 마커
    </p>
    <div
      ref="el"
      class="mt-3 h-64 w-full"
    />
    <div class="mt-2 flex flex-wrap gap-3 sk-meta">
      <span>● hard = MDC 변경(epoch 리셋)</span>
      <span>○ soft = BM/PM(MDC 불변)</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TrendPoint, EpochMarker } from '~/composables/useTttmApi'

const props = defineProps<{ trend: TrendPoint[], markers: EpochMarker[] }>()

const el = ref<HTMLDivElement | null>(null)

const byTool = computed(() => {
  const map = new Map<string, TrendPoint[]>()
  for (const p of props.trend) {
    if (!map.has(p.eqp_id)) map.set(p.eqp_id, [])
    map.get(p.eqp_id)!.push(p)
  }
  return map
})

const chartOption = computed<EChartsOption>(() => {
  const dates = [...new Set(props.trend.map(p => p.date))].sort()
  const series: EChartsOption['series'] = [...byTool.value.entries()].map(([eqp, pts]) => ({
    name: eqp,
    type: 'line',
    showSymbol: true,
    data: dates.map(d => pts.find(p => p.date === d)?.skew ?? null),
    markPoint: {
      symbolSize: 14,
      data: props.markers
        .filter(m => m.eqp_id === eqp)
        .map(m => ({
          name: m.kind === 'hard' ? 'PM' : 'BM',
          xAxis: m.date,
          yAxis: pts.find(p => p.date === m.date)?.skew ?? 0,
          itemStyle: {
            color: m.kind === 'hard' ? '#b91c1c' : 'transparent',
            borderColor: '#b45309',
            borderWidth: 1
          },
          value: m.kind === 'hard' ? 'PM' : 'BM'
        }))
    }
  }))

  return {
    grid: { top: 16, right: 16, bottom: 28, left: 40 },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, type: 'scroll' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'skew (nm)', scale: true },
    series
  }
})

useEchart(el, chartOption)
</script>
