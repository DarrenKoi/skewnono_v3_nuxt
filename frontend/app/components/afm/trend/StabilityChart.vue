<template>
  <AfmCard
    icon="i-lucide-crosshair"
    title="포인트 안정도"
  >
    <p
      v-if="!stability.some(s => s.sd !== null)"
      class="flex h-48 items-center justify-center text-center sk-body"
    >
      포인트 값이 있는 측정이 2건 이상이어야 측정 간 편차를 냅니다.
    </p>
    <template v-else>
      <div
        ref="chartEl"
        class="h-48 w-full"
      />
      <p class="mt-2 sk-meta leading-relaxed">
        포인트마다 {{ count }}건의 값을 모아 측정 간 STDEV를 냅니다. 유독 높은 포인트는 그 자리만 흔들린다는 뜻이고, 전부 비슷하게 높으면 wafer 전체가 lot 따라 움직인 것입니다.
      </p>
      <div
        v-if="unstable.length"
        class="mt-2 flex flex-wrap gap-1.5"
      >
        <span
          v-for="u in unstable"
          :key="u.point"
          class="inline-flex h-6 items-center gap-1.5 rounded-(--sk-r-sidebar) bg-(--sk-bad-soft) px-2 text-xs font-semibold text-(--sk-bad) ring-1 ring-(--sk-bad-border) ring-inset"
        >
          포인트 {{ u.point }}
          <span class="font-mono tabular-nums">σ {{ fmt2(u.sd) }}</span>
        </span>
      </div>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TrendRow } from '~/utils/afmTrend'
import { SK_SCALE } from '~/utils/chartPalette'

const props = defineProps<{
  rows: TrendRow[]
  exportName: string
}>()

const sk = useChartPalette()

const series = computed(() => props.rows.flatMap(row =>
  row.stats?.points.size ? [{ key: row.entry.key, points: row.stats.points }] : []
))
const count = computed(() => series.value.length)
const stability = computed(() => pointStability(pointMatrix(series.value, 'mean', null)))
const unstable = computed(() => stability.value.filter(s => s.unstable))

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 52, right: 12, top: 28, bottom: 32 },
  tooltip: {
    trigger: 'item',
    formatter: (p: unknown) => {
      const { name, value } = p as { name: string, value: number | null }
      return `포인트 ${escapeHtml(name)}<br/>측정 간 STDEV ${fmt2(value)} nm`
    }
  },
  xAxis: { type: 'category', data: stability.value.map(s => s.point), axisLabel: { ...CHART_AXIS_LABEL, hideOverlap: true }, axisTick: { show: false } },
  yAxis: { type: 'value', name: 'σ (nm)', nameTextStyle: CHART_LEGEND_LABEL, axisLabel: CHART_AXIS_LABEL },
  series: [{
    type: 'bar',
    barCategoryGap: '30%',
    data: stability.value.map(s => ({ value: s.sd, itemStyle: { color: s.unstable ? SK_SCALE[4] : sk.value.seriesSoft } }))
  }]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
