<template>
  <div
    ref="chartEl"
    role="img"
    class="w-full"
    :class="heightClass"
    :aria-label="ariaLabel"
  />
  <span class="sr-only">{{ ariaLabel }}</span>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { paramValues } from '~/utils/msrRows'
import { mean as meanOf, quantileSorted, iqrFences } from '~/utils/stats'
import { SK_CHART } from '~/utils/chartPalette'

// One group's raw values for the grouped box/violin comparison.
export interface DistributionGroup {
  label: string
  values: number[]
}

// CD distribution for one parameter, in four shapes: histogram, ECDF, box plot,
// or a (mirrored-density) violin. The active shape is driven by the panel toggle.
//
// Value source (first that is set wins):
//   • `groups` — per-group value lists; Box renders one box per group (the group
//     distribution). Hist/ECDF/Violin pool the groups' values.
//   • `values` — an explicit value list (the exact-pair explorer passes the
//     paired Y values so the marginal matches the active query, not all rows).
//   • `rows` + `parameter` — the legacy path (the `set` branch), unchanged.
const props = withDefaults(defineProps<{
  rows?: MsrFileRow[]
  parameter?: string
  unit: string
  values?: number[]
  groups?: DistributionGroup[]
  // 'Hist' | 'ECDF' | 'Box' | 'Violin' — kept as a plain string so callers can
  // bind the PanelFrame toggle value directly without an in-template type cast.
  mode?: string
  // Chart height utility. Defaults to a fixed h-72; the dashboard passes h-full
  // so the chart fills a flex panel.
  heightClass?: string
}>(), {
  mode: 'Hist',
  heightClass: 'h-72'
})

const BIN_COUNT = 12

// Deterministic per-point jitter for the box-plot raw-point overlay: hashes
// (category index, point index) into a stable pseudo-random value in [0, 1).
// Same visual spread as Math.random() but stable across reactive recomputes.
function jitterHash(catIndex: number, pointIndex: number): number {
  let h = (catIndex * 73856093) ^ (pointIndex * 19349663)
  h = (h ^ (h >>> 13)) * 1274126177
  h = h ^ (h >>> 16)
  return ((h >>> 0) % 10000) / 10000
}

// Pooled values — the flat list every non-grouped shape reads from.
const values = computed<number[]>(() => {
  if (props.groups) return props.groups.flatMap(g => g.values).filter(v => Number.isFinite(v))
  if (props.values) return props.values.filter(v => Number.isFinite(v))
  return paramValues(props.rows ?? [], props.parameter ?? '')
})

// null, not 0: an empty parameter has no mean to mark. A markline/label
// consumer must suppress rendering on null rather than plotting a fabricated
// CD = 0 — see governing principle in app/utils/msrRows.ts / stats.ts.
const mean = computed<number | null>(() => {
  const v = values.value
  return v.length ? meanOf(v) : null
})

// Shared binning for histogram + violin.
const bins = computed(() => {
  const vals = values.value
  if (vals.length === 0) return { centers: [] as number[], counts: [] as number[] }
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const width = span / BIN_COUNT
  const counts = new Array(BIN_COUNT).fill(0)
  for (const v of vals) {
    const idx = Math.min(BIN_COUNT - 1, Math.floor((v - min) / width))
    counts[idx] += 1
  }
  const centers = counts.map((_, i) => min + width * (i + 0.5))
  return { centers, counts }
})

// Five-number summary with Tukey-fenced whiskers for a set of values.
const fiveNumber = (vals: number[]): number[] | null => {
  const sorted = [...vals].sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const f = iqrFences(sorted)!
  const inliers = sorted.filter(v => v >= f.lower && v <= f.upper)
  return [
    inliers[0] ?? sorted[0]!,
    f.q1,
    quantileSorted(sorted, 0.5),
    f.q3,
    inliers[inliers.length - 1] ?? sorted[sorted.length - 1]!
  ]
}

// ECDF: sorted value → cumulative proportion (i+1)/n, drawn as a step line. The
// default comparison candidate alongside the histogram — it reads the shape of a
// distribution (and shifts between groups) without binning artefacts.
const ecdfPoints = computed<[number, number][]>(() => {
  const sorted = [...values.value].sort((a, b) => a - b)
  const n = sorted.length
  return sorted.map((v, i) => [v, (i + 1) / n])
})

const histOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: {
    type: 'category',
    data: bins.value.centers.map(c => c.toFixed(1)),
    axisLabel: { fontSize: 11 },
    name: props.unit ? `${label.value} (${props.unit})` : label.value,
    nameLocation: 'middle',
    nameGap: 26,
    nameTextStyle: { fontSize: 11 }
  },
  yAxis: { type: 'value', axisLabel: { fontSize: 11 }, splitLine: { show: false }, name: 'count', nameTextStyle: { fontSize: 11 } },
  series: [{
    type: 'bar',
    data: bins.value.counts,
    barWidth: '90%',
    itemStyle: { color: SK_CHART.seriesSoft, borderRadius: [2, 2, 0, 0] }
  }]
}))

const ecdfOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const p = (Array.isArray(params) ? params[0] : params) as { value: number[] }
      const v = p.value
      return `${label.value}: <b>${v[0]?.toFixed(3)}</b><br/>F(x): <b>${((v[1] ?? 0) * 100).toFixed(0)}%</b>`
    }
  },
  grid: { left: 40, right: 16, top: 24, bottom: 28, containLabel: true },
  xAxis: {
    type: 'value',
    scale: true,
    name: props.unit ? `${label.value} (${props.unit})` : label.value,
    nameLocation: 'middle',
    nameGap: 24,
    nameTextStyle: { fontSize: 11 },
    axisLabel: { fontSize: 11 }
  },
  yAxis: { type: 'value', min: 0, max: 1, axisLabel: { fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }, name: 'F(x)', nameTextStyle: { fontSize: 11 } },
  series: [{
    type: 'line',
    step: 'end',
    showSymbol: false,
    lineStyle: { color: SK_CHART.series, width: 1.5 },
    areaStyle: { color: SK_CHART.seriesSoft, opacity: 0.35 },
    data: ecdfPoints.value
  }]
}))

// Box plot. With `groups` it renders one box PER group (the group distribution);
// otherwise a single box. Raw points are overlaid (jittered) and the N of each
// category is carried in the axis label, per the spec's "raw points or N".
const boxCategories = computed<{ label: string, values: number[] }[]>(() => {
  if (props.groups) return props.groups
  return [{ label: props.parameter ?? label.value, values: values.value }]
})

const boxOption = computed<EChartsOption>(() => {
  const cats = boxCategories.value
  const boxData = cats.map(c => fiveNumber(c.values)).filter((d): d is number[] => d != null)
  // Jittered raw points per category index — the honest overlay of every value.
  // Jitter is a deterministic hash of (category index, point index) rather than
  // Math.random(), so points hold their horizontal position across reactive
  // recomputes instead of reshuffling on every re-render.
  const rawPoints: [number, number][] = []
  cats.forEach((c, i) => {
    c.values.forEach((v, j) => rawPoints.push([i + (jitterHash(i, j) - 0.5) * 0.3, v]))
  })
  return {
    tooltip: { trigger: 'item' },
    grid: { left: 48, right: 16, top: 24, bottom: 34, containLabel: true },
    xAxis: {
      type: 'category',
      data: cats.map(c => `${c.label} (n=${c.values.length})`),
      axisLabel: { fontSize: 11, interval: 0 }
    },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 11 }, name: props.unit, nameTextStyle: { fontSize: 11 } },
    series: [
      {
        type: 'boxplot',
        data: boxData,
        itemStyle: { color: SK_CHART.sand, borderColor: SK_CHART.series }
      },
      {
        type: 'scatter',
        symbolSize: 4,
        itemStyle: { color: SK_CHART.brand, opacity: 0.35 },
        data: rawPoints,
        tooltip: { show: false }
      }
    ]
  }
})

// Violin: mirror the binned density around the value axis (±count/2). Pools any
// groups. The sample N is annotated so a thin violin is never misread as certain.
const violinOption = computed<EChartsOption>(() => {
  const { centers, counts } = bins.value
  const top = centers.map((c, i) => [c, counts[i]! / 2])
  const bottom = centers.map((c, i) => [c, -counts[i]! / 2])
  return {
    tooltip: { trigger: 'axis' },
    title: { text: `n = ${values.value.length}`, right: 8, top: 4, textStyle: { fontSize: 11, color: SK_CHART.muted } },
    grid: { left: 36, right: 16, top: 24, bottom: 28, containLabel: true },
    xAxis: {
      type: 'value',
      scale: true,
      name: props.unit ? `${label.value} (${props.unit})` : label.value,
      nameLocation: 'middle',
      nameGap: 24,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 }
    },
    yAxis: { type: 'value', axisLabel: { show: false }, splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
    series: [
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: SK_CHART.series, width: 1 }, areaStyle: { color: SK_CHART.seriesSoft, opacity: 0.5 }, data: top },
      { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: SK_CHART.series, width: 1 }, areaStyle: { color: SK_CHART.seriesSoft, opacity: 0.5 }, data: bottom }
    ]
  }
})

// Axis label: the parameter name, falling back to a neutral '값' for the
// explicit-values / grouped paths that carry no single parameter identity.
const label = computed(() => props.parameter || '값')

// Screen-reader text alternative: the active shape's headline numbers, mirroring
// what a sighted user reads off the axis/title (n, and mean where one exists).
const ariaLabel = computed(() => {
  const n = values.value.length
  const meanStr = mean.value != null ? `, 평균 ${mean.value.toFixed(3)}${props.unit}` : ''
  if (props.mode === 'Box') {
    const cats = boxCategories.value
    const total = cats.reduce((sum, c) => sum + c.values.length, 0)
    return `${label.value} 박스플롯: ${cats.length}개 그룹, 전체 n=${total}`
  }
  if (props.mode === 'ECDF') return `${label.value} 누적분포(ECDF): n=${n}${meanStr}`
  if (props.mode === 'Violin') return `${label.value} 바이올린 분포: n=${n}${meanStr}`
  return `${label.value} 히스토그램: n=${n}${meanStr}`
})

const option = computed<EChartsOption>(() => {
  if (props.mode === 'ECDF') return ecdfOption.value
  if (props.mode === 'Box') return boxOption.value
  if (props.mode === 'Violin') return violinOption.value
  return histOption.value
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)

defineExpose({ mean })
</script>
