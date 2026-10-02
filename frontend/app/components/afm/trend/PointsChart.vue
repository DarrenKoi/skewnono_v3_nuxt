<template>
  <AfmCard
    icon="i-lucide-chart-spline"
    title="포인트 × 측정"
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2.5">
        <div
          class="flex items-center gap-1"
          role="group"
          aria-label="값 보기"
        >
          <SkChip
            v-for="m in MODES"
            :key="m.value"
            size="sm"
            tone="ink"
            :label="m.label"
            :active="mode === m.value"
            @click="mode = m.value"
          />
        </div>
        <span class="h-4.5 w-px bg-(--sk-border)" />
        <label class="flex items-center gap-1.5">
          <span class="sk-label">기준</span>
          <USelect
            v-model="baseline"
            :items="BASELINES"
            size="xs"
            class="min-w-28"
            aria-label="기준"
          />
        </label>
      </div>
    </template>

    <p
      v-if="!matrix.rows.length"
      class="flex h-72 items-center justify-center sk-body"
    >
      포인트별 data 행이 있는 측정이 없습니다.
    </p>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
    <p class="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1 sk-meta">
      <span>{{ block }} · {{ column }} · 포인트 {{ matrix.points.length }}{{ recipe ? ` · ${recipe}만` : '' }}</span>
      <span>— 다른 측정</span>
      <span class="text-(--sk-ink)">— 선택한 측정</span>
      <span class="text-(--sk-brand)">┄ 기준 ({{ baselineLabel }})</span>
      <span>{{ selectedRow ? `선택: ${selectedRow.entry.lot}·${selectedRow.entry.slot} ${shortTime(selectedRow.entry.time)}` : '선택한 측정에 이 블록이 없습니다' }}</span>
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption, SeriesOption } from 'echarts'
import type { PointBaseline, TrendRow } from '~/utils/afmTrend'
import { SK_SCALE } from '~/utils/chartPalette'

const props = defineProps<{
  // Rows in time order; only those with point values draw a line.
  rows: TrendRow[]
  block: string
  column: string
  // Set in a mixed group: the one recipe whose points are compared.
  recipe?: string
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [key: string] }>()

const MODES = [{ value: 'value', label: '값' }, { value: 'delta', label: '기준 대비 Δ' }] as const
const BASELINES: { value: PointBaseline, label: string }[] = [
  { value: 'mean', label: '그룹 평균' },
  { value: 'first', label: '첫 측정' },
  { value: 'selected', label: '선택한 측정' }
]
const mode = ref<'value' | 'delta'>('value')
const baseline = ref<PointBaseline>('mean')

const OUT = SK_SCALE[4]
const sk = useChartPalette()

const drawn = computed(() => props.rows.filter(row => row.stats?.points.size))
const matrix = computed(() => pointMatrix(
  drawn.value.map(row => ({ key: row.entry.key, points: row.stats!.points })),
  baseline.value,
  props.selected
))
const selectedRow = computed(() => drawn.value.find(row => row.entry.key === props.selected))
const baselineLabel = computed(() =>
  matrix.value.baselineUsed === 'selected' && selectedRow.value
    ? `${selectedRow.value.entry.lot}·${selectedRow.value.entry.slot}`
    : BASELINES.find(b => b.value === matrix.value.baselineUsed)!.label
)

const shown = (value: number | null, i: number) => {
  const base = matrix.value.baseline[i] ?? null
  if (value === null) return null
  if (mode.value === 'value') return value
  return base === null ? null : value - base
}

const label = (row: TrendRow) => `${row.entry.lot}·${row.entry.slot}`

const chartOption = computed<EChartsOption>(() => {
  const { points, rows } = matrix.value
  const series: SeriesOption[] = rows.map((row, r) => {
    const on = row.key === props.selected
    const color = on ? sk.value.ink : drawn.value[r]!.out ? OUT : sk.value.muted
    return {
      name: label(drawn.value[r]!),
      type: 'line',
      // Every line keeps small symbols: a click on a bare line carries no datum.
      symbolSize: on ? 7 : 4,
      z: on ? 6 : 2,
      lineStyle: { color, width: on ? 2.2 : 1.2, opacity: on ? 1 : 0.45 },
      itemStyle: { color, opacity: on ? 1 : 0.45 },
      emphasis: { focus: 'none', lineStyle: { width: 2.2, opacity: 1 } },
      data: row.values.map((value, i) => shown(value, i))
    }
  })
  series.push({
    name: '기준',
    type: 'line',
    symbol: 'none',
    silent: true,
    z: 4,
    lineStyle: { color: OUT, type: 'dashed', width: 1.6 },
    data: points.map((_, i) => mode.value === 'value' ? matrix.value.baseline[i] ?? null : 0)
  })
  return {
    grid: { left: 64, right: 20, top: 24, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params: unknown) => {
        const list = params as { dataIndex: number, seriesIndex: number, value: number | null }[]
        const i = list[0]?.dataIndex ?? 0
        const sel = rows.findIndex(row => row.key === props.selected)
        const fmtVal = (v: number | null | undefined) => v == null ? '–' : fmt2(v)
        return [
          `<b>포인트 ${escapeHtml(points[i] ?? '')}</b>`,
          sel >= 0 ? `${escapeHtml(label(drawn.value[sel]!))}: ${fmtVal(shown(rows[sel]!.values[i] ?? null, i))}` : '',
          `기준: ${fmtVal(mode.value === 'value' ? matrix.value.baseline[i] : 0)}`,
          `측정 ${rows.filter(row => row.values[i] != null).length}건`
        ].filter(Boolean).join('<br/>')
      }
    },
    xAxis: { type: 'category', data: points, name: 'Point', nameLocation: 'middle', nameGap: 28, nameTextStyle: CHART_LEGEND_LABEL, axisLabel: CHART_AXIS_LABEL, axisTick: { show: false } },
    yAxis: { type: 'value', scale: true, name: mode.value === 'value' ? props.column : `Δ ${props.column}`, nameTextStyle: CHART_LEGEND_LABEL, axisLabel: CHART_AXIS_LABEL },
    series
  }
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, {
  exportName: props.exportName,
  onDataIndex: (_dataIndex, seriesIndex) => {
    const key = matrix.value.rows[seriesIndex]?.key
    if (key) emit('select', key)
  }
})
</script>
