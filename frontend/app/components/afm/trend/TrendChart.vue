<template>
  <AfmCard
    icon="i-lucide-chart-no-axes-combined"
    title="시계열"
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2.5">
        <div
          class="flex items-center gap-1"
          role="group"
          aria-label="보기"
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
          <span class="sk-label">띠</span>
          <USelect
            v-model="band"
            :items="BANDS"
            size="xs"
            class="min-w-28"
            aria-label="띠"
            :disabled="mode === 'box'"
          />
        </label>
        <UCheckbox
          v-model="showLimits"
          label="관리선"
          size="sm"
        />
      </div>
    </template>

    <p
      v-if="!option"
      class="flex h-80 items-center justify-center sk-body"
    >
      {{ mode === 'box' ? '포인트별 data 행이 있는 측정이 없습니다.' : '이 블록·항목의 값이 없습니다.' }}
    </p>
    <div
      v-else
      ref="chartEl"
      class="h-80 w-full"
    />
    <p class="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1 sk-meta">
      <span>{{ block }} · {{ column }} · {{ mode === 'box' ? '분포' : stat }}</span>
      <span class="text-(--sk-brand)">● 관리선 밖</span>
      <span>▬ μ</span>
      <span>┄ UCL / LCL = μ ± 3σ (σ = {{ limitStat }}들의 MAD 기반 강건 표준편차 · 이상치가 관리선을 넓히지 않음)</span>
      <span v-if="note">{{ note }}</span>
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption, MarkLineComponentOption, SeriesOption } from 'echarts'
import type { RecipeCentre, TrendRow, TrendStat } from '~/utils/afmTrend'
import { SK_SCALE } from '~/utils/chartPalette'

const props = defineProps<{
  rows: TrendRow[]
  recipes: string[]
  centres: Map<string, RecipeCentre>
  block: string
  column: string
  stat: TrendStat
  selected: string | null
  exportName: string
}>()
const emit = defineEmits<{ select: [key: string] }>()
const showLimits = defineModel<boolean>('showLimits', { required: true })

const MODES = [{ value: 'line', label: '추세' }, { value: 'box', label: '박스플롯' }] as const
const BANDS = [{ value: 'minmax', label: 'MIN – MAX' }, { value: 'sigma', label: '± 1 STDEV' }, { value: 'none', label: '없음' }]
const mode = ref<'line' | 'box'>('line')
const band = ref('minmax')

// Terracotta marks a value outside its recipe's limits, in both themes.
const OUT = SK_SCALE[4]
const sk = useChartPalette()
const { palette, surface } = useEchartsTheme()
// Palette index 1 is skipped: most themes make it the warm accent, which would
// read as "outside the limits".
const recipeColor = (i: number) => i === 0 ? sk.value.series : palette.value[(i + 1) % palette.value.length] ?? sk.value.series

// A box plot is a picture of point values in nm, so its limits are the MEANs'.
const boxLimits = computed(() => props.stat === 'MEAN')
const limitStat = computed(() => mode.value === 'box' ? 'MEAN' : props.stat)

const note = computed(() => {
  if (mode.value === 'box') {
    const lacking = props.rows.filter(row => row.value !== null && !row.stats?.box).length
    return `상자 = Q1–Q3 · 수염 = MIN–MAX · ◆ = MEAN (포인트별 data 행에서 계산)${lacking ? ` · data 행이 없는 ${lacking}건 제외` : ''}${boxLimits.value ? '' : ' · 관리선은 통계 = MEAN에서만'}`
  }
  if (props.stat !== 'MEAN') return '띠는 MEAN에서만 그립니다'
  return band.value === 'none' ? '' : `띠 = ${band.value === 'minmax' ? 'MIN – MAX' : 'MEAN ± 1 STDEV'}`
})

const markLine = (recipe: string): MarkLineComponentOption | undefined => {
  const limits = props.centres.get(recipe)?.limits
  if (!showLimits.value || !limits) return undefined
  return {
    symbol: 'none',
    silent: true,
    label: { ...CHART_LEGEND_LABEL, position: 'insideEndTop', formatter: p => `${p.name} ${Number(p.value).toFixed(2)}` },
    data: [
      { name: 'μ', yAxis: limits.mu, lineStyle: { color: sk.value.muted, width: 1.5, type: 'solid' } },
      { name: 'UCL', yAxis: limits.ucl, lineStyle: { color: OUT, type: 'dashed' } },
      { name: 'LCL', yAxis: limits.lcl, lineStyle: { color: OUT, type: 'dashed' } }
    ]
  }
}

// The value axis stretches to the drawn limits: ECharts sizes it from the
// series alone, so an LCL below every value would sit off the chart. A fixed
// bound is printed as its first tick, so it is rounded to half a decade.
const limitAxis = (recipes: string[]) => {
  const drawn = showLimits.value ? recipes.flatMap(r => props.centres.get(r)?.limits ?? []) : []
  if (!drawn.length) return {}
  const bounds = (v: { min: number, max: number }) => {
    const lo = Math.min(v.min, ...drawn.map(l => l.lcl))
    const hi = Math.max(v.max, ...drawn.map(l => l.ucl))
    const step = 10 ** Math.floor(Math.log10(hi - lo || 1)) / 2
    return [+(Math.floor(lo / step) * step).toFixed(6), +(Math.ceil(hi / step) * step).toFixed(6)] as const
  }
  return { min: (v: { min: number, max: number }) => bounds(v)[0], max: (v: { min: number, max: number }) => bounds(v)[1] }
}

const rowByKey = computed(() => new Map(props.rows.map(row => [row.entry.key, row])))

const tooltip = (key: string) => {
  const row = rowByKey.value.get(key)
  if (!row) return ''
  const { entry } = row
  return [
    `<b>${escapeHtml(entry.lot)} · ${escapeHtml(entry.slot)}</b>`,
    `${shortTime(entry.time)} · ${escapeHtml(entry.recipe)}`,
    `${props.stat}: ${fmt2(row.value)} nm`,
    `Δμ: ${row.delta === null ? '–' : formatSignedNm(row.delta, 2)}`
  ].join('<br/>')
}

const lineChart = (): { option: EChartsOption, keys: (string | null)[][] } | null => {
  const series: SeriesOption[] = []
  const keys: (string | null)[][] = []
  const withBand = props.stat === 'MEAN' && band.value !== 'none'
  props.recipes.forEach((recipe, i) => {
    const rows = props.rows.filter(row => row.entry.recipe === recipe && row.value !== null)
    if (!rows.length) return
    const color = recipeColor(i)
    if (withBand) {
      const edges = rows.flatMap(({ entry, stats }) => {
        const s = stats!
        const lo = band.value === 'minmax' ? s.MIN : s.MEAN !== null && s.STDEV !== null ? s.MEAN - s.STDEV : null
        const hi = band.value === 'minmax' ? s.MAX : s.MEAN !== null && s.STDEV !== null ? s.MEAN + s.STDEV : null
        return lo === null || hi === null ? [] : [{ t: entry.time, lo, hi }]
      })
      // Two stacked lines; 'all' so a negative lower edge still stacks, and the
      // area pinned in emphasis/blur so hovering cannot erase it.
      const area = { color: SK_SCALE[0], opacity: 0.16 }
      const base = { type: 'line' as const, stack: `band-${i}`, stackStrategy: 'all' as const, symbol: 'none', silent: true, lineStyle: { opacity: 0 } }
      series.push({ ...base, name: `band-lo-${i}`, data: edges.map(e => [e.t, e.lo]) })
      series.push({ ...base, name: `band-${i}`, areaStyle: area, emphasis: { areaStyle: area }, blur: { areaStyle: area }, data: edges.map(e => [e.t, e.hi - e.lo]) })
      keys.push([], [])
    }
    series.push({
      name: recipe,
      type: 'line',
      symbolSize: 9,
      z: 5,
      lineStyle: { color, width: 2 },
      itemStyle: { color },
      data: rows.map(row => ({
        value: [row.entry.time, row.value],
        key: row.entry.key,
        itemStyle: {
          color: row.out ? OUT : row.entry.key === props.selected ? sk.value.ink : color,
          borderColor: row.entry.key === props.selected ? sk.value.ink : 'transparent',
          borderWidth: 2
        }
      })),
      markLine: markLine(recipe)
    })
    keys.push(rows.map(row => row.entry.key))
  })
  if (!keys.some(k => k.length)) return null
  // Only recipes that drew a series under this block × column.
  const named = props.recipes.filter(recipe => series.some(s => s.name === recipe))
  return {
    keys,
    option: {
      grid: { left: 64, right: 80, top: props.recipes.length > 1 ? 48 : 24, bottom: 64 },
      legend: props.recipes.length > 1 ? { top: 0, left: 'center', data: named, textStyle: CHART_LEGEND_LABEL } : undefined,
      tooltip: { trigger: 'item', formatter: (p: unknown) => tooltip((p as { data?: { key?: string } }).data?.key ?? '') },
      xAxis: { type: 'time', axisLabel: { ...CHART_AXIS_LABEL, formatter: '{MM}/{dd} {HH}:{mm}', hideOverlap: true }, splitLine: { show: false } },
      yAxis: { type: 'value', scale: true, ...limitAxis(props.recipes), name: props.column, nameTextStyle: CHART_LEGEND_LABEL, axisLabel: CHART_AXIS_LABEL },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
      series
    }
  }
}

const boxChart = (): { option: EChartsOption, keys: (string | null)[][] } | null => {
  const rows = props.rows.filter(row => row.stats?.box)
  if (!rows.length) return null
  const out = (row: TrendRow) => boxLimits.value && row.out
  const colorIndex = (row: TrendRow) => props.recipes.indexOf(row.entry.recipe)
  const keys = rows.map(row => row.entry.key)
  return {
    keys: [keys, keys],
    option: {
      grid: { left: 64, right: 80, top: 24, bottom: 72 },
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const { dataIndex } = p as { dataIndex: number }
          const row = rows[dataIndex]
          const b = row?.stats?.box
          if (!row || !b) return ''
          return `${tooltip(row.entry.key)}<br/>min ${fmt2(b.min)} · Q1 ${fmt2(b.q1)} · med ${fmt2(b.median)} · Q3 ${fmt2(b.q3)} · max ${fmt2(b.max)}`
        }
      },
      xAxis: { type: 'category', data: rows.map(row => `${row.entry.lot}·${row.entry.slot}`), axisLabel: { ...CHART_AXIS_LABEL, rotate: 30 }, axisTick: { show: false } },
      yAxis: { type: 'value', scale: true, ...limitAxis(boxLimits.value && props.recipes.length === 1 ? props.recipes : []), name: props.column, nameTextStyle: CHART_LEGEND_LABEL, axisLabel: CHART_AXIS_LABEL },
      series: [
        {
          type: 'boxplot',
          boxWidth: [10, 26],
          data: rows.map((row) => {
            const b = row.stats!.box!
            const on = row.entry.key === props.selected
            const edge = out(row) ? OUT : on ? sk.value.ink : recipeColor(colorIndex(row))
            return {
              value: [b.min, b.q1, b.median, b.q3, b.max],
              itemStyle: { color: surface.value.surface, borderColor: edge, borderWidth: on ? 2 : 1.2 }
            }
          }),
          markLine: boxLimits.value && props.recipes.length === 1 ? markLine(props.recipes[0]!) : undefined
        },
        {
          type: 'line',
          symbol: 'diamond',
          symbolSize: 8,
          z: 5,
          lineStyle: { opacity: 0 },
          itemStyle: { color: sk.value.ink },
          data: rows.map(row => row.stats!.MEAN)
        }
      ]
    }
  }
}

const chart = computed(() => mode.value === 'box' ? boxChart() : lineChart())
const option = computed(() => chart.value?.option ?? null)

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, computed(() => option.value ?? {}), {
  exportName: props.exportName,
  onDataIndex: (dataIndex, seriesIndex) => {
    const key = chart.value?.keys[seriesIndex]?.[dataIndex]
    if (key) emit('select', key)
  }
})
</script>
