<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="sk-title">
        skew 트렌드 · BM/PM 마커
      </p>
      <span
        v-if="span"
        class="sk-meta"
      >{{ span }}</span>
    </div>
    <div
      ref="el"
      class="mt-2 h-64 w-full"
    />
    <p class="mt-1.5 sk-field-label">
      ● hard = MDC 변경(epoch 리셋) · ○ soft = BM/PM(MDC 불변)
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TrendPoint, EpochMarker } from '~/composables/useTttmApi'

const props = defineProps<{ trend: TrendPoint[], markers: EpochMarker[] }>()

const el = ref<HTMLDivElement | null>(null)

// The window the series actually cover, from the data rather than from a
// hardcoded "최근 5주": the payload decides how far back the trend goes, and a
// caption that names a span the data does not have is worse than none.
const span = computed(() => {
  const dates = [...new Set(props.trend.map(p => p.date))].sort()
  if (dates.length < 2) return ''
  return `${dates[0]} ~ ${dates[dates.length - 1]}`
})

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
