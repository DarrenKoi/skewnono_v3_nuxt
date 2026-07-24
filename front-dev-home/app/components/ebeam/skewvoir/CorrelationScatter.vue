<template>
  <div
    ref="chartEl"
    role="img"
    tabindex="0"
    class="h-72 w-full"
    :aria-label="ariaLabel"
  />
  <span class="sr-only">{{ ariaLabel }}</span>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { PairedPoint } from '~/utils/skewvoirAnalysis/relationships'
import { measuredRows } from '~/utils/msrRows'
import { pearson, spearman, fitLine } from '~/utils/stats'

// Param-vs-param correlation within one measurement.
//
// Two entry modes, both EXACT-pair (never index-paired):
//   • `points` — pre-joined PairedPoint[] from utils/skewvoirAnalysis/relationships
//     (the single-MSR explorer). Each point carries its `chip`, so a scatter click
//     emits `focus(chip)` to drive the linked site + SEM preview.
//   • `rows` + paramX/paramY — the legacy focus-only path (the `set` branch), which
//     pairs the two parameters' CD values by site key here. Kept UNCHANGED so the
//     set-scope view still renders; its points carry no chip, so clicks are inert.
const props = defineProps<{
  rows?: MsrFileRow[]
  points?: PairedPoint[]
  paramX: string
  paramY: string
  unitX: string
  unitY: string
  // When the join is unavailable (0 pairs / constant axis), the reason to show
  // instead of a fabricated R². Optional; falls back to the derived label.
  readinessReason?: string | null
}>()

const emit = defineEmits<{ focus: [chip: string] }>()

const sk = useChartPalette()

// Legacy rows path: pair the two parameters by (chip + sequence) here.
const legacyPairs = computed<[number, number][]>(() => {
  const rows = measuredRows(props.rows ?? [])
  const xBySite = new Map<string, number>()
  for (const r of rows) {
    if (r.parameter === props.paramX) xBySite.set(`${r.chip_number}#${r.sequence}`, r.cd_value)
  }
  const out: [number, number][] = []
  for (const r of rows) {
    if (r.parameter !== props.paramY) continue
    const x = xBySite.get(`${r.chip_number}#${r.sequence}`)
    if (x != null) out.push([x, r.cd_value])
  }
  return out
})

// The active pairs, either from the pre-joined points or the legacy rows path.
const pairs = computed<[number, number][]>(() =>
  props.points ? props.points.map(p => [p.x, p.y]) : legacyPairs.value
)

// ECharts scatter data. When points are supplied, tag each datum's `name` with
// its chip so useEchart's click handler (which forwards params.name) can emit
// focus(chip) — the link that moves the focused site + SEM preview.
const scatterData = computed(() =>
  props.points
    ? props.points.map(p => ({ value: [p.x, p.y] as [number, number], name: p.chip }))
    : pairs.value
)

const r = computed(() => pearson(pairs.value))
const r2 = computed(() => (r.value == null ? null : r.value * r.value))
const rho = computed(() => spearman(pairs.value))
const sampleN = computed(() => pairs.value.length)

// pearson returns null for TWO distinct reasons: n < 3 (too few pairs) or zero
// variance on either axis (plenty of pairs, but a constant CD). Conflating them
// under "표본 부족" would lie when n is large — label each honestly.
const noAnswerLabel = computed(() =>
  props.readinessReason ?? (sampleN.value < 3 ? '표본 부족' : '분산 없음')
)

const fitLinePoints = computed<[number, number][]>(() => fitLine(pairs.value) ?? [])

// Screen-reader text alternative: the two parameters plotted and the same
// R²/ρ/n headline the on-chart title shows sighted users.
const ariaLabel = computed(() => {
  const stat = r2.value != null
    ? `R² ${r2.value.toFixed(3)}${rho.value != null ? `, ρ ${rho.value.toFixed(3)}` : ''}`
    : noAnswerLabel.value
  return `${props.paramX} 대 ${props.paramY} 산점도: n=${sampleN.value}, ${stat}`
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = params as { value: number[], name?: string }
      const v = p.value
      const chipLine = p.name ? `site: <b>${p.name}</b><br/>` : ''
      return `${chipLine}${props.paramX}: <b>${v[0]}</b><br/>${props.paramY}: <b>${v[1]}</b>`
    }
  },
  title: r2.value != null
    ? {
        text: `R² = ${r2.value.toFixed(3)} · n = ${sampleN.value}${rho.value != null ? ` · ρ = ${rho.value.toFixed(3)}` : ''}`,
        right: 8,
        top: 4,
        textStyle: { fontSize: 11, color: sk.value.brand }
      }
    : { text: `${noAnswerLabel.value} · n = ${sampleN.value}`, right: 8, top: 4, textStyle: { fontSize: 11, color: sk.value.muted } },
  grid: { left: 44, right: 16, top: 24, bottom: 36, containLabel: true },
  xAxis: {
    type: 'value',
    scale: true,
    name: props.unitX ? `${props.paramX} (${props.unitX})` : props.paramX,
    nameLocation: 'middle',
    nameGap: 24,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unitY ? `${props.paramY} (${props.unitY})` : props.paramY,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  series: [
    {
      type: 'scatter',
      symbolSize: 7,
      itemStyle: { color: sk.value.seriesSoft, opacity: 0.7 },
      data: scatterData.value
    },
    {
      type: 'line',
      smooth: false,
      showSymbol: false,
      lineStyle: { color: sk.value.brand, width: 2 },
      data: fitLinePoints.value,
      tooltip: { show: false },
      silent: true
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: chip => emit('focus', chip) })
</script>
