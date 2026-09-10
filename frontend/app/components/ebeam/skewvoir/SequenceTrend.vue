<template>
  <div>
    <!-- Tool legend — the SAME ranking + palette as the trend chart above it
         (utils/skewvoirAnalysis/toolColors), so one tool never wears two colors
         on one screen. -->
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
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: chip.color }"
        />
        {{ chip.label }}
      </span>
    </div>
    <div
      ref="chartEl"
      class="h-72 w-full"
    />
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { SequenceGroup } from '~/utils/skewvoirAnalysis/timeSeries'
import { formatChip, sequenceAxisBounds } from '~/utils/skewvoirAnalysis/timeSeries'
import { rankToolColors, toolLegendChips } from '~/utils/skewvoirAnalysis/toolColors'
import { nearestPoint } from '~/utils/chartNearest'

// cd_value across measurement order WITHIN each MSR, the whole set overlaid —
// one line per measurement, colored by tool, so intra-wafer drift can be read
// against the other tools' profiles instead of in isolation.
//
// The x axis is the recipe's measurement ORDER, and each step is a move to a
// different die — so a point is "chip (col,row), measured Nth", and the tooltip
// says so. Without the die, a rise across the axis is unattributable: it reads
// as tool drift over time when it may be a plain across-wafer signature.
const props = defineProps<{
  groups: SequenceGroup[]
  /** The focus measurement's line is emphasized, not isolated. */
  focusMsr: string | null
  parameter: string
  unit: string
}>()

const sk = useChartPalette()

// One color slot per measurement drawn, same rule as the trend chart: a tool's
// weight in the ranking is how many LINES it contributes here.
const toolColor = computed(() => rankToolColors(props.groups.map(g => g.eqpId)))
const legendChips = computed(() => toolLegendChips(toolColor.value))

// Axis bounds from the DATA rather than from zero — see sequenceAxisBounds.
// Null when nothing is drawn, which leaves the axis to ECharts.
const xBounds = computed(() => sequenceAxisBounds(props.groups))

const option = computed<EChartsOption>(() => ({
  tooltip: {
    // `item`, not `axis`: sequences from different measurements interleave, so
    // an axis tooltip would list every line's nearest point as if they shared
    // an x. The hovered symbol names its own measurement.
    trigger: 'item',
    formatter: (params) => {
      const p = Array.isArray(params) ? params[0] : params
      // dim2 is chip_number, carried through untouched by ECharts.
      const hit = p as { seriesIndex?: number, value?: [number, number, string] }
      const group = props.groups[hit.seriesIndex ?? -1]
      if (!group || !hit.value) return ''
      return [
        group.label,
        `eqp: ${group.eqpId}`,
        `seq ${hit.value[0]} · chip (${formatChip(hit.value[2] ?? '')})`,
        `${props.parameter}: <b>${hit.value[1]}</b> ${props.unit}`
      ].join('<br/>')
    }
  },
  grid: { left: 40, right: 16, top: 24, bottom: 32, containLabel: true },
  xAxis: {
    type: 'value',
    name: 'sequence (chip 이동 순서)',
    nameLocation: 'middle',
    nameGap: 24,
    // `scale: true` releases the axis from the origin; the explicit bounds then
    // pin it to the drawn range. Both are needed — `scale` alone still lets
    // ECharts nice-round outward, which re-introduces the very dead space a
    // high-numbered sequence run is being rescued from.
    scale: true,
    min: xBounds.value?.min,
    max: xBounds.value?.max,
    axisLabel: { fontSize: 10 },
    nameTextStyle: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    name: props.unit,
    axisLabel: { fontSize: 10 },
    splitLine: { show: false },
    nameTextStyle: { fontSize: 10 }
  },
  // Series order MUST match props.groups — the tooltip indexes back into it.
  series: props.groups.map(g => ({
    name: g.label,
    type: 'line' as const,
    data: g.points,
    smooth: false,
    showSymbol: true,
    symbolSize: g.msr === props.focusMsr ? 5 : 3.5,
    lineStyle: {
      width: g.msr === props.focusMsr ? 2.5 : 1.2,
      color: toolColor.value.get(g.eqpId) ?? sk.value.series,
      opacity: g.msr === props.focusMsr ? 1 : 0.7
    },
    itemStyle: { color: toolColor.value.get(g.eqpId) ?? sk.value.series },
    emphasis: { scale: 1.6 },
    z: g.msr === props.focusMsr ? 3 : 2
  }))
}))

const chartEl = ref<HTMLDivElement | null>(null)

// This chart draws the smallest symbols in the app — 3.5px, 5px on the focus
// line — so an item-triggered tooltip was effectively unreachable: the reader
// had to land inside a 3.5px dot on one of a dozen overlaid lines. The pick
// below hands the tooltip a radius, the same way the trend chart's does.
//
// Series order matches props.groups exactly (the option's series is a straight
// .map over it), which is what makes seriesIndex here a valid ECharts address —
// the same invariant the tooltip formatter already relies on.
const pickable = computed(() =>
  props.groups.flatMap((group, seriesIndex) =>
    group.points.map((point, dataIndex) => ({
      x: point[0],
      y: point[1],
      item: { seriesIndex, dataIndex }
    }))
  )
)

useEchart(chartEl, option, {
  // A tighter radius than the 44px default: lines here are dense and overlaid,
  // so a generous pick would routinely describe a neighbouring measurement's
  // point rather than the one under the cursor.
  onGridHover: detail => nearestPoint(pickable.value, detail, { maxDistancePx: 22 })
})
</script>
