<template>
  <div>
    <!-- Tool legend. Color here means EQUIPMENT and nothing else: unlike the
         Time-Series chart there is no verdict channel on these marks, so the
         swatch is a filled dot — it matches the mark it explains. -->
    <div
      v-if="legendChips.length"
      class="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1"
    >
      <span
        v-for="chip in legendChips"
        :key="chip.label"
        class="inline-flex items-center gap-1 sk-meta"
      >
        <span
          class="size-2.5 shrink-0 rounded-full"
          :style="{ backgroundColor: chip.color }"
        />
        {{ chip.label }}
      </span>
    </div>
    <div
      ref="chartEl"
      role="img"
      tabindex="0"
      class="h-72 w-full"
      :aria-label="ariaLabel"
    />
    <span class="sr-only">{{ ariaLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AcrossMsrResult, AcrossMsrPoint } from '~/utils/skewvoirAnalysis/acrossMsr'
import { rankToolColors, toolLegendChips } from '~/utils/skewvoirAnalysis/toolColors'
import { SK_SITE_OVERFLOW } from '~/utils/chartPalette'
import { fitLine } from '~/utils/stats'
import { nearestPoint } from '~/utils/chartNearest'

// One MSR is one point. The pairing, the coefficients and the per-tool
// stratification all come pre-computed from utils/skewvoirAnalysis/acrossMsr —
// this component only draws them.
const props = defineProps<{ result: AcrossMsrResult }>()

const emit = defineEmits<{ select: [msr: string] }>()

const sk = useChartPalette()

// Ranked over the DRAWN points, not the loaded set: a measurement dropped for a
// missing axis value must not spend an identity color (same rule as
// TimeSeriesChart, one tool never wears two colors across the workspace).
//
// `''` is the module's "this measurement has no tool identity" sentinel, not a
// tool. buildAcrossMsrOutcome already refuses to build a stratum from it — so
// ranking it here would give a tool that does not exist a palette color and an
// empty-labelled legend chip, and the chart would show a group the stratified
// table declines to name. Filtered at the source of BOTH the ranking and the
// grouping; the points themselves still draw, under UNNAMED_LABEL below.
const namedIds = computed(() => props.result.points.map(p => p.eqpId).filter(Boolean))
const toolColor = computed(() => rankToolColors(namedIds.value))
const legendChips = computed(() => {
  const chips = toolLegendChips(toolColor.value)
  // Appended, never ranked in: the unnamed group is an absence of identity, so
  // it sits after every named tool rather than competing with them for a slot.
  if (unnamed.value.length) chips.push({ label: UNNAMED_LABEL, color: SK_SITE_OVERFLOW })
  return chips
})

const axisName = (axis: { label: string, unit: string } | null): string => {
  if (!axis) return ''
  return axis.unit ? `${axis.label} (${axis.unit})` : axis.label
}

// One series per tool, in the legend's own order, so the grouping the eye reads
// is the same grouping the stratified coefficients were computed over.
const byTool = computed(() => {
  const groups = new Map<string, AcrossMsrPoint[]>()
  for (const id of toolColor.value.keys()) groups.set(id, [])
  for (const p of props.result.points) {
    if (!p.eqpId) continue
    groups.get(p.eqpId)?.push(p)
  }
  return groups
})

// Measurements whose meas-hist row could not be resolved (a deep-linked msr, a
// row outside the loaded history). They are real measurements and stay on the
// chart, but under a named neutral rather than borrowing a tool's color.
const UNNAMED_LABEL = '장비 미상'
const unnamed = computed(() => props.result.points.filter(p => !p.eqpId))

// The pooled OLS line is drawn ONLY when the pooled coefficient was actually
// published. With a suppressed coefficient (too few MSRs, a constant axis) a
// fitted line would assert exactly the trend the summary just declined to state.
const pooledFit = computed<[number, number][]>(() => {
  if (props.result.pooled.reason !== null) return []
  return fitLine(props.result.points.map(p => [p.x, p.y] as [number, number])) ?? []
})

const ariaLabel = computed(() => {
  const { pooled, points, x, y } = props.result
  const stat = pooled.pearson != null
    ? `전체 r ${pooled.pearson.toFixed(3)}`
    : (pooled.reason ?? '평가 불가')
  return `${x?.label ?? ''} 대 ${y?.label ?? ''} MSR 단위 산점도: MSR ${points.length}개, ${stat}`
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = params as { data?: { point?: AcrossMsrPoint } }
      const pt = p.data?.point
      if (!pt) return ''
      return `<b>${pt.label}</b><br/>${props.result.x?.label ?? 'X'}: <b>${pt.x}</b><br/>${props.result.y?.label ?? 'Y'}: <b>${pt.y}</b>`
    }
  },
  grid: { left: 44, right: 16, top: 12, bottom: 36, containLabel: true },
  xAxis: {
    type: 'value',
    scale: true,
    name: axisName(props.result.x),
    nameLocation: 'middle',
    nameGap: 24,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: axisName(props.result.y),
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  series: [
    ...[...byTool.value.entries()].map(([eqpId, points]) => ({
      type: 'scatter' as const,
      name: eqpId,
      symbolSize: 9,
      itemStyle: { color: toolColor.value.get(eqpId), opacity: 0.85 },
      data: points.map(point => ({ value: [point.x, point.y] as [number, number], point }))
    })),
    ...(unnamed.value.length
      ? [{
          type: 'scatter' as const,
          name: UNNAMED_LABEL,
          symbolSize: 9,
          itemStyle: { color: SK_SITE_OVERFLOW, opacity: 0.85 },
          data: unnamed.value.map(point => ({ value: [point.x, point.y] as [number, number], point }))
        }]
      : []),
    {
      type: 'line' as const,
      smooth: false,
      showSymbol: false,
      lineStyle: { color: sk.value.brand, width: 2 },
      data: pooledFit.value,
      tooltip: { show: false },
      silent: true
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)

// Clicking a dot moves the workspace focus onto that measurement — the set-scope
// counterpart of the single-scope "click a site to focus it" gesture. The pick
// happens in screen space because X and Y hold different units.
const clickable = computed(() =>
  props.result.points.map(point => ({ x: point.x, y: point.y, item: point.msr }))
)

useEchart(chartEl, option, {
  onGridClick: (detail) => {
    const msr = nearestPoint(clickable.value, detail)
    if (msr) emit('select', msr)
  }
})
</script>
