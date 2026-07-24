<template>
  <div
    ref="chartEl"
    class="w-full"
    :class="heightClass"
  />
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { radialYExtent, type RadialBandMode, type RadialProfileResult } from '~/utils/radialAnalysis'
import { SK_STATE } from '~/utils/chartPalette'

const props = withDefaults(defineProps<{
  profile: RadialProfileResult
  parameter: string
  unit: string
  focusedSequence: number | null
  selectedSeqs?: number[]
  band?: RadialBandMode
  colorBySector?: boolean
  showResiduals?: boolean
  heightClass?: string
}>(), {
  band: 'iqr',
  selectedSeqs: () => [],
  colorBySector: false,
  showResiduals: false,
  heightClass: 'h-full min-h-[9rem]'
})
const emit = defineEmits<{ focus: [sequence: number] }>()

// Shared shape for the main + residual value axes (both x and y), so the
// residual push doesn't fight the main axis's literal type.
interface ValueAxisConfig {
  type: 'value'
  scale?: boolean
  min?: number
  max?: number
  name?: string
  nameLocation?: 'middle'
  nameGap?: number
  nameTextStyle?: { fontSize: number }
  axisLabel?: { fontSize: number, formatter?: (value: number) => string }
  gridIndex?: number
}

const sk = useChartPalette()

// Wafer sector identities. E/N take theme colors because they only need to be
// told apart; W/S keep the semantic amber and green they have always used.
const sectorColors = computed<Record<string, string>>(() => ({
  E: sk.value.series,
  N: sk.value.brand,
  W: SK_STATE.warn,
  S: SK_STATE.ok
}))

const scatterData = computed(() => props.profile.points.map(point => ({
  name: String(point.sequence),
  value: [point.radius, point.value],
  fitted: point.fitted,
  residual: point.residual,
  sector: point.sector,
  itemStyle: props.colorBySector && point.sector
    ? { color: sectorColors.value[point.sector] ?? sk.value.seriesSoft, opacity: 0.78 }
    : { color: sk.value.seriesSoft, opacity: 0.72 }
})))

const focused = computed(() => scatterData.value.filter(point => Number(point.name) === props.focusedSequence))

const selectedPts = computed(() => {
  const picked = new Set(props.selectedSeqs)
  return scatterData.value.filter(point => picked.has(Number(point.name)))
})

const bandPoints = computed(() => {
  if (props.band === 'iqr') {
    return props.profile.bins.map(bin => ({ radius: bin.radius, lower: bin.q1, upper: bin.q3 }))
  }
  if (props.band === 'confidence') {
    return props.profile.curve.flatMap(point =>
      point.confidenceLower != null && point.confidenceUpper != null
        ? [{ radius: point.radius, lower: point.confidenceLower, upper: point.confidenceUpper }]
        : [])
  }
  if (props.band === 'prediction') {
    return props.profile.curve.flatMap(point =>
      point.predictionLower != null && point.predictionUpper != null
        ? [{ radius: point.radius, lower: point.predictionLower, upper: point.predictionUpper }]
        : [])
  }
  return []
})

const bandSeries = computed(() => {
  if (!bandPoints.value.length || props.band === 'none') return []
  return [
    {
      name: 'band lower',
      type: 'line' as const,
      stack: 'radial-band',
      data: bandPoints.value.map(point => [point.radius, point.lower]),
      lineStyle: { opacity: 0 },
      symbol: 'none',
      tooltip: { show: false },
      silent: true,
      z: 1
    },
    {
      name: props.band === 'iqr' ? 'radial IQR' : `${props.band} 95%`,
      type: 'line' as const,
      stack: 'radial-band',
      data: bandPoints.value.map(point => [point.radius, point.upper - point.lower]),
      lineStyle: { opacity: 0 },
      areaStyle: { color: props.band === 'iqr' ? sk.value.sand : sk.value.series, opacity: 0.2 },
      symbol: 'none',
      tooltip: { show: false },
      silent: true,
      z: 1
    }
  ]
})

const medianSeries = computed(() => props.profile.bins.length
  ? [{
      name: 'radial median',
      type: 'line' as const,
      smooth: false,
      showSymbol: true,
      symbolSize: 4,
      lineStyle: { color: sk.value.muted, width: 1, type: 'dashed' as const },
      itemStyle: { color: sk.value.muted },
      data: props.profile.bins.map(bin => [bin.radius, bin.median]),
      tooltip: { show: false },
      silent: true,
      z: 2
    }]
  : [])

const residualSeries = computed(() => {
  if (!props.showResiduals || props.profile.status !== 'fitted') return []
  return [{
    name: 'residual',
    type: 'scatter' as const,
    xAxisIndex: 1,
    yAxisIndex: 1,
    symbolSize: 6,
    data: props.profile.points.flatMap(point => point.residual == null
      ? []
      : [{
          name: String(point.sequence),
          value: [point.radius, point.residual],
          fitted: point.fitted,
          residual: point.residual,
          sector: point.sector,
          itemStyle: props.colorBySector && point.sector
            ? { color: sectorColors.value[point.sector] ?? sk.value.series }
            : { color: sk.value.series }
        }]),
    markLine: {
      silent: true,
      symbol: 'none',
      label: { show: false },
      lineStyle: { color: sk.value.muted, width: 1 },
      data: [{ yAxis: 0 }]
    },
    z: 3
  }]
})

const option = computed<EChartsOption>(() => {
  const hasResiduals = props.showResiduals && props.profile.status === 'fitted'
  const mainGrid = hasResiduals
    ? { left: 52, right: 20, top: 20, height: '55%', containLabel: true }
    : { left: 40, right: 44, top: 30, bottom: 36, containLabel: true }
  const xAxes: ValueAxisConfig[] = [{
    type: 'value',
    min: props.profile.metrics.n ? props.profile.metrics.radiusMin : 0,
    max: props.profile.metrics.n ? props.profile.metrics.radiusMax : undefined,
    name: hasResiduals ? '' : 'distance from center (mm)',
    nameLocation: 'middle',
    nameGap: 24,
    nameTextStyle: { fontSize: 11 },
    axisLabel: { fontSize: 10, formatter: (value: number) => String(Math.round(value)) }
  }]
  // Explicit y window from the plotted data (points + band + curve) so a new
  // data selection ALWAYS re-fits the axis — `scale: true` alone left the
  // window pinned across selections.
  const yExtent = radialYExtent(props.profile, props.band ?? 'none')
  const yAxes: ValueAxisConfig[] = [{
    type: 'value',
    scale: true,
    min: yExtent?.min,
    max: yExtent?.max,
    name: props.unit || props.parameter,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10, formatter: (value: number) => value.toFixed(2) }
  }]
  if (hasResiduals) {
    xAxes.push({
      type: 'value',
      min: props.profile.metrics.radiusMin,
      max: props.profile.metrics.radiusMax,
      name: 'distance from center (mm)',
      nameLocation: 'middle',
      nameGap: 24,
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 },
      gridIndex: 1
    })
    yAxes.push({
      type: 'value',
      scale: true,
      name: `residual${props.unit ? ` (${props.unit})` : ''}`,
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 },
      gridIndex: 1
    })
  }

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const data = (params as { data?: { name?: string, value?: number[], fitted?: number | null, residual?: number | null, sector?: string } }).data
        if (!data?.value || !data.name) return ''
        const lines = [
          `seq ${data.name}${data.sector ? ` · sector ${data.sector}` : ''}`,
          `r: <b>${data.value[0]?.toFixed(2)}</b> mm`
        ]
        if (data.residual != null && (params as { seriesName?: string }).seriesName === 'residual') {
          lines.push(`residual: <b>${data.residual.toFixed(4)}</b> ${props.unit}`)
        } else {
          lines.push(`${props.parameter}: <b>${data.value[1]?.toFixed(4)}</b> ${props.unit}`)
          if (data.fitted != null) lines.push(`fit: ${data.fitted.toFixed(4)} · residual: ${data.residual?.toFixed(4)}`)
        }
        return lines.join('<br/>')
      }
    },
    legend: props.colorBySector
      ? { data: [], show: false }
      : undefined,
    grid: hasResiduals
      ? [mainGrid, { left: 52, right: 20, top: '72%', bottom: 38, containLabel: true }]
      : mainGrid,
    xAxis: xAxes,
    yAxis: yAxes,
    series: [
      ...bandSeries.value,
      ...medianSeries.value,
      {
        name: props.parameter,
        type: 'scatter',
        symbolSize: 7,
        data: scatterData.value,
        z: 3
      },
      {
        name: 'fit',
        type: 'line',
        smooth: false,
        showSymbol: false,
        lineStyle: { color: sk.value.brand, width: 2 },
        data: props.profile.curve.map(point => [point.radius, point.value]),
        tooltip: { show: false },
        silent: true,
        z: 4
      },
      {
        name: 'selected',
        type: 'scatter',
        symbolSize: 18,
        data: selectedPts.value,
        itemStyle: { color: sk.value.series, opacity: 0.18, borderColor: sk.value.series, borderWidth: 1.5 },
        tooltip: { show: false },
        silent: true,
        z: 5
      },
      {
        name: 'focused',
        type: 'scatter',
        symbolSize: 16,
        data: focused.value,
        itemStyle: { color: 'transparent', borderColor: sk.value.ink, borderWidth: 3 },
        tooltip: { show: false },
        silent: true,
        z: 6
      },
      ...residualSeries.value
    ]
  }
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, { onClick: name => emit('focus', Number(name)) })
</script>
