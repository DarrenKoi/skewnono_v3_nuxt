<template>
  <div class="trend-chart">
    <header class="trend-chart__head">
      <div>
        <p class="trend-chart__eyebrow">
          trend · {{ focusedLot ? focusedLot : '-' }}
        </p>
        <h4 class="trend-chart__title">
          {{ title }}
        </h4>
      </div>
      <div
        class="trend-chart__toggle"
        role="tablist"
        aria-label="trend mode"
      >
        <button
          v-for="tab in modeTabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="mode === tab.value"
          class="trend-chart__tab"
          :class="mode === tab.value ? 'trend-chart__tab--on' : ''"
          @click="mode = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
    </header>

    <div
      v-if="!trendData.hasData"
      class="trend-chart__empty"
    >
      <UIcon
        name="i-lucide-line-chart"
        class="h-4 w-4"
      />
      <span>{{ text.empty }}</span>
    </div>
    <div
      v-else
      ref="chartEl"
      class="trend-chart__canvas"
    />

    <p class="trend-chart__hint">
      {{ mode === 'stacked' ? text.hintStacked : text.hintLines }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useColorMode } from '#imports'
import type { EChartsOption } from 'echarts'
import type { TopLevelFormatterParams } from 'echarts/types/dist/shared'
import { paraColors, paraColorsDark } from './healthTokens'
import type { SummaryBucketKey, RecipeTrendResponse } from '~/composables/useRecipeStatisticsApi'
import { extractParaTrend, formatTrendTick, type ParaKey } from '~/utils/paraTrendSeries'
import { CHART_AXIS_LABEL, CHART_LEGEND_LABEL } from '~/utils/chartType'

type TrendMode = 'lines' | 'stacked'

const props = withDefaults(defineProps<{
  trend: RecipeTrendResponse | null | undefined
  bucket: SummaryBucketKey
  focusedLot: string | null
  title?: string
}>(), {
  title: '파라미터 추이'
})

const text = {
  empty: 'lot 을 선택하면 추이가 표시됩니다',
  hintLines: '범례를 클릭하면 해당 파라미터만 볼 수 있습니다. 세로축은 실제 recipe 개수입니다.',
  hintStacked: '영역의 맨 위 경계가 para_all 합계입니다.'
} as const

const modeTabs: Array<{ value: TrendMode, label: string }> = [
  { value: 'lines', label: '개별' },
  { value: 'stacked', label: '누적' }
]

const mode = ref<TrendMode>('lines')

const colorMode = useColorMode()
const { surface } = useEchartsTheme()
const palette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const chartEl = ref<HTMLDivElement | null>(null)

const trendData = computed(() =>
  extractParaTrend(props.trend, props.bucket, props.focusedLot)
)

// A distinct symbol per series, so identity never rests on colour alone. The
// ramp is a single hue by design (see healthTokens), which makes shape the
// thing that separates two lines where they cross.
const SYMBOLS: Record<ParaKey, string> = {
  para_16: 'circle',
  para_13: 'rect',
  para_9: 'triangle',
  para_5: 'diamond'
}

const escapeHtml = (s: string) => s.replace(/[&<>"']/g, c => (
  c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : '&#39;'
))

const formatTooltip = (raw: TopLevelFormatterParams) => {
  const arr = Array.isArray(raw) ? raw : [raw]
  if (arr.length === 0) return ''

  const idx = typeof arr[0]?.dataIndex === 'number' ? arr[0].dataIndex : -1
  const date = trendData.value.dates[idx] ?? ''
  const total = idx >= 0 ? trendData.value.totals[idx] : null

  const header = `<div style="font-weight:600">${escapeHtml(date)}</div>`
  const lines = arr.map((p) => {
    // marker is a rich-text token object only when textStyle.rich is set; we
    // never set it, so the runtime value is always the HTML <span> string.
    const marker = typeof p.marker === 'string' ? p.marker : ''
    const name = typeof p.seriesName === 'string' ? p.seriesName : ''
    const value = p.value === null || p.value === undefined ? '—' : String(p.value)
    return '<div style="display:flex;justify-content:space-between;gap:16px">'
      + `<span>${marker}${escapeHtml(name)}</span>`
      + `<span style="font-variant-numeric:tabular-nums">${escapeHtml(value)}</span>`
      + '</div>'
  }).join('')

  const totalRow = total === null
    ? ''
    : '<div style="display:flex;justify-content:space-between;gap:16px;'
      + 'margin-top:4px;padding-top:4px;border-top:1px solid rgba(127,127,127,0.3);font-weight:600">'
      + '<span>para_all</span>'
      + `<span style="font-variant-numeric:tabular-nums">${total}</span>`
      + '</div>'

  return header + lines + totalRow
}

const option = computed<EChartsOption>(() => {
  const data = trendData.value
  const pal = palette.value
  const stacked = mode.value === 'stacked'

  return {
    grid: { left: 8, right: 44, top: 34, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: formatTooltip
    },
    legend: {
      top: 4,
      // Clear of useEchart's PNG-download button, which is 26px wide at
      // top:6/right:6 and fades in on hover — at right:0 it lands on the
      // last legend entry.
      right: 38,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: CHART_LEGEND_LABEL,
      data: data.series.map(s => s.label)
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.dates.map(formatTrendTick),
      axisLabel: CHART_AXIS_LABEL
    },
    yAxis: {
      type: 'value',
      name: 'recipe 수',
      nameTextStyle: { ...CHART_LEGEND_LABEL, align: 'left' },
      minInterval: 1,
      axisLabel: CHART_AXIS_LABEL,
      splitLine: { lineStyle: { opacity: 0.35 } }
    },
    series: data.series.map(s => ({
      id: s.key,
      name: s.label,
      type: 'line' as const,
      data: s.values,
      // Nulls stay holes. Bridging them would invent a measurement for a week
      // the lot was never sampled in.
      connectNulls: false,
      stack: stacked ? 'total' : undefined,
      symbol: SYMBOLS[s.key],
      symbolSize: 8,
      itemStyle: { color: pal[s.key] },
      // Stacked: a 2px stroke in the surface colour separates adjacent bands so
      // two neighbouring steps of one hue never bleed into each other.
      // Lines: the stroke IS the series.
      lineStyle: stacked
        ? { width: 2, color: surface.value.surface }
        : { width: 2, color: pal[s.key] },
      areaStyle: stacked ? { color: pal[s.key], opacity: 1 } : undefined,
      // Direct end-labels in lines mode — the second non-colour identity cue.
      endLabel: stacked
        ? { show: false }
        : {
            show: true,
            ...CHART_LEGEND_LABEL,
            fontWeight: 'bold' as const,
            color: pal[s.key],
            formatter: s.label
          },
      // Hover must not restyle the stack. ECharts' emphasis/blur states drop the
      // area fill on a stacked line series, so the composition vanishes at the
      // exact moment the tooltip is being read. Pin both states to the base
      // style; isolation stays available through the legend.
      emphasis: { disabled: true },
      blur: { areaStyle: { opacity: stacked ? 1 : 0 } }
    }))
  }
})

useEchart(chartEl, option, { exportName: 'para-trend' })
</script>

<style scoped>
.trend-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.trend-chart__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.trend-chart__eyebrow {
  font: 500 9.5px/1.2 var(--font-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--sk-ink-subtle);
}

.trend-chart__title {
  font: 600 12.5px/1.2 var(--font-sans);
  color: var(--sk-ink);
  margin-top: 2px;
}

.trend-chart__toggle {
  display: inline-flex;
  background: var(--sk-muted-surface);
  border-radius: 7px;
  padding: 2px;
  box-shadow: inset 0 0 0 1px var(--sk-border);
}

.trend-chart__tab {
  font: 600 10.5px/1 var(--font-sans);
  padding: 4px 10px;
  border-radius: 5px;
  color: var(--sk-ink-muted);
  cursor: pointer;
  transition: all 120ms ease;
}

.trend-chart__tab--on {
  background: var(--sk-surface);
  color: var(--sk-ink);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.trend-chart__canvas {
  width: 100%;
  height: 320px;
}

.trend-chart__hint {
  font: 500 10px/1.4 var(--font-sans);
  color: var(--sk-ink-subtle);
}

.trend-chart__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px 12px;
  font: 500 11px/1.4 var(--font-sans);
  color: var(--sk-ink-subtle);
}
</style>
