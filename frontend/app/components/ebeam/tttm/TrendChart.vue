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
      class="mt-2 h-80 w-full"
    />
    <p class="mt-1.5 sk-field-label">
      실선 = hard(MDC 변경 · epoch 리셋) · 점선 = soft(BM/PM · MDC 불변) ·
      범례를 누르면 그 장비의 선을 숨기고 · 휠/슬라이더로 기간을 확대합니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption, LineSeriesOption } from 'echarts'
import { SK_STATE } from '~/utils/chartPalette'
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

// Semantic, not theme-driven (chartPalette's rule for SK_STATE): a hard
// marker is an epoch reset and reads as severity; a soft one is a warning
// that something was touched.
const markerColor = (kind: EpochMarker['kind']) =>
  kind === 'hard' ? SK_STATE.bad : SK_STATE.warn

// A VERTICAL LINE per marker, on the tool's own series — so hiding a tool
// through the legend hides its markers with it, and a line spans the whole
// plot rather than sitting as a 14px dot on one point that the eye skipped.
const markLineFor = (eqp: string): LineSeriesOption['markLine'] => {
  const own = props.markers.filter(m => m.eqp_id === eqp)
  if (!own.length) return undefined
  return {
    silent: true,
    symbol: 'none',
    animation: false,
    label: { show: true, position: 'insideEndTop', fontSize: 10, distance: 4 },
    data: own.map(m => ({
      xAxis: m.date,
      name: m.label,
      lineStyle: {
        color: markerColor(m.kind),
        width: m.kind === 'hard' ? 2 : 1.5,
        type: m.kind === 'hard' ? 'solid' : 'dashed'
      },
      label: {
        formatter: `${eqp} ${m.kind === 'hard' ? 'PM' : 'BM'}`,
        color: markerColor(m.kind)
      }
    }))
  }
}

const chartOption = computed<EChartsOption>(() => {
  const series: LineSeriesOption[] = [...byTool.value.entries()].map(([eqp, pts]) => ({
    name: eqp,
    type: 'line',
    showSymbol: true,
    // A time axis rather than a category one: a marker can fall on a day no
    // tool measured, and a category axis has no place to draw it.
    data: [...pts].sort((a, b) => a.date.localeCompare(b.date)).map(p => [p.date, p.skew]),
    markLine: markLineFor(eqp)
  }))

  return {
    grid: { top: 36, right: 16, bottom: 52, left: 44 },
    tooltip: { trigger: 'axis' },
    // Clicking an entry hides that tool's line (ECharts' default `selectedMode`);
    // the selector adds 전체/반전 so one tool can be isolated in two clicks.
    legend: {
      top: 0,
      type: 'scroll',
      selector: [{ type: 'all', title: '전체' }, { type: 'inverse', title: '반전' }],
      selectorLabel: { fontSize: 10 }
    },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: 'skew (nm)', scale: true },
    // Stable literal: useEchart carries the live window across rebuilds by
    // index (utils/chartZoom), so the two entries must keep their positions.
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 16, bottom: 8 }
    ],
    series
  }
})

useEchart(el, chartOption)
</script>
