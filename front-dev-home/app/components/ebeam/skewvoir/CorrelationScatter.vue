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
import type { PairedPoint } from '~/utils/skewvoirAnalysis/relationships'
import { pearson, spearman, fitLine } from '~/utils/stats'

// Param-vs-param correlation renders only pre-paired points. Relationship joins
// belong to utils/skewvoirAnalysis/relationships so every scope shares one
// chip-aware pairing contract; point chips also drive linked focus behavior.
const props = defineProps<{
  points: PairedPoint[]
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

const pairs = computed<[number, number][]>(() =>
  props.points.map(point => [point.x, point.y])
)

const scatterData = computed(() =>
  props.points.map(point => ({
    value: [point.x, point.y] as [number, number],
    name: point.chip
  }))
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
