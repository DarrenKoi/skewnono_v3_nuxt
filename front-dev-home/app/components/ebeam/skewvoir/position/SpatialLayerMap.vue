<template>
  <EbeamSkewvoirPanelFrame
    title="Spatial Layer Map"
    :meta="meta"
    icon="i-lucide-layers"
    body-class="flex flex-col gap-2"
  >
    <template #actions>
      <!-- Layer switcher: raw / median-centered / residual / failure. -->
      <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
        <button
          v-for="opt in layerOptions"
          :key="opt.key"
          type="button"
          class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
          :class="opt.key === layer
            ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
            : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
          :disabled="opt.disabled"
          :title="opt.disabled ? '좌표/추세 부족' : opt.label"
          @click="layer = opt.key"
        >
          {{ opt.label }}
        </button>
      </div>
      <UTooltip text="측정 순서(scan path) 오버레이 — 공간 패턴이 측정 순서와 혼재됐는지 확인">
        <UButton
          :color="scanPath ? 'primary' : 'neutral'"
          :variant="scanPath ? 'soft' : 'ghost'"
          size="xs"
          icon="i-lucide-spline"
          aria-label="측정 순서 경로"
          :disabled="spatial.readiness.coordinates === 'unavailable'"
          @click="scanPath = !scanPath"
        />
      </UTooltip>
    </template>

    <div
      v-if="spatial.readiness.coordinates === 'unavailable'"
      class="flex flex-1 flex-col items-center justify-center gap-1 px-4 text-center sk-body"
    >
      <UIcon
        name="i-lucide-map-pin-off"
        class="h-6 w-6 text-(--sk-ink-subtle)"
      />
      <span>좌표 정보가 없어 raw 레이어와 표만 제공됩니다.</span>
      <span class="text-[11px] text-(--sk-ink-subtle)">{{ spatial.readiness.reason }}</span>
    </div>
    <template v-else>
      <div class="grid min-h-0 flex-1 place-items-center">
        <div class="aspect-square w-full max-w-[22rem]">
          <div
            ref="chartEl"
            role="img"
            tabindex="0"
            class="h-full w-full"
            :aria-label="ariaLabel"
          />
        </div>
      </div>
      <span class="sr-only">{{ ariaLabel }}</span>
      <div class="flex flex-col items-center gap-1">
        <EbeamSkewvoirColorScaleBar
          :min="range.min"
          :max="range.max"
          :unit="activeLayerUnit"
        />
        <div class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-mono text-[11px] text-(--sk-ink-muted)">
          <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span>측정 실패</span>
          <span
            v-if="scanPath"
            class="inline-flex items-center gap-1"
          ><span class="text-(--sk-brand)">—</span>측정 순서</span>
        </div>
      </div>
    </template>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { SpatialResult, SpatialLayerKey } from '~/utils/skewvoirAnalysis/spatial'
import type { WaferGeometry } from '~/utils/waferGeometry'
import { SK_SCALE, SK_STATE } from '~/utils/chartPalette'
import { nearestPoint } from '~/utils/chartNearest'

const props = defineProps<{
  spatial: SpatialResult
  geo: WaferGeometry
  focusedSite: string | null
  unit: string
}>()
const emit = defineEmits<{ focus: [chip: string] }>()

const sk = useChartPalette()

type Layer = SpatialLayerKey
const layer = ref<Layer>('raw')
const scanPath = ref(false)

const layerOptions = computed<{ key: Layer, label: string, disabled: boolean }[]>(() => [
  { key: 'raw', label: 'Raw', disabled: false },
  { key: 'centered', label: 'Centered', disabled: false },
  { key: 'residual', label: 'Residual', disabled: props.spatial.readiness.radialTrend !== 'ok' },
  { key: 'failure', label: 'Failure', disabled: props.spatial.failures.length === 0 }
])

// Reset to raw if the active layer becomes unavailable (e.g. parameter change
// drops the radial trend).
watch(() => props.spatial, () => {
  const active = layerOptions.value.find(o => o.key === layer.value)
  if (active?.disabled) layer.value = 'raw'
})

const activeLayerUnit = computed(() => (layer.value === 'raw' ? props.unit : props.unit))

// Placed measured sites (posMm present) carrying the active layer's value.
interface LayerPoint { chip: string, seq: number, x: number, y: number, value: number, sector: string | null }
const points = computed<LayerPoint[]>(() => {
  const out: LayerPoint[] = []
  for (const s of props.spatial.sites) {
    if (!s.posMm) continue
    const value = layer.value === 'centered'
      ? s.centered
      : layer.value === 'residual'
        ? s.residual
        : s.raw
    if (value == null || !Number.isFinite(value)) continue
    out.push({ chip: s.chip, seq: s.sequence, x: s.posMm[0], y: s.posMm[1], value, sector: s.sector })
  }
  return out
})

// Failures placed on the wafer (✕).
const failurePoints = computed(() =>
  props.spatial.failures.flatMap(f => (f.posMm ? [{ name: f.chip, value: [f.posMm[0], f.posMm[1]] }] : []))
)

// Symmetric range for diverging layers (centered / residual); data range for raw.
const range = computed(() => {
  const vals = points.value.map(p => p.value)
  if (vals.length === 0) return { min: -1, max: 1 }
  if (layer.value === 'raw') {
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    return min === max ? { min: min - 0.5, max: max + 0.5 } : { min, max }
  }
  const m = Math.max(0.5, ...vals.map(Math.abs))
  return { min: -m, max: m }
})

const scanPathData = computed(() => {
  if (!scanPath.value) return []
  return [...points.value].sort((a, b) => a.seq - b.seq).map(p => [p.x, p.y])
})

const focusPoint = computed(() =>
  points.value.filter(p => p.chip === props.focusedSite).map(p => ({ name: p.chip, value: [p.x, p.y] }))
)

const waferRadius = computed(() => props.geo.radiusMm || 150)
const axisMax = computed(() => waferRadius.value * 1.03)
const waferOutline = computed<[number, number][]>(() => {
  const R = waferRadius.value
  const steps = 120
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = (i / steps) * Math.PI * 2
    return [Number((R * Math.cos(t)).toFixed(3)), Number((R * Math.sin(t)).toFixed(3))] as [number, number]
  })
})

const meta = computed(() => {
  const label = layer.value === 'centered' ? '중앙값 대비' : layer.value === 'residual' ? '추세 잔차' : layer.value === 'failure' ? '측정 실패' : 'raw'
  return `${label} · ${points.value.length} sites`
})

// Screen-reader text alternative for the wafer scatter canvas: active layer,
// site count, and the value range the color scale is currently mapped to —
// the same numbers the color bar next to the chart shows.
const ariaLabel = computed(() => {
  const layerLabel = layer.value === 'centered' ? '중앙값 대비' : layer.value === 'residual' ? '추세 잔차' : layer.value === 'failure' ? '측정 실패' : 'raw'
  const u = activeLayerUnit.value
  const r = range.value
  return `공간 레이어 맵: ${layerLabel} 레이어, ${points.value.length}개 측정 지점, 범위 ${r.min.toFixed(2)} ~ ${r.max.toFixed(2)}${u ? ` ${u}` : ''}`
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = params as { name?: string, value?: number[] }
      const hit = points.value.find(pt => pt.chip === p.name)
      if (!hit) return `chip ${p.name}`
      return [
        `chip ${hit.chip}${hit.sector ? ` · ${hit.sector}` : ''} · seq ${hit.seq}`,
        `${layer.value}: <b>${hit.value.toFixed(3)}</b> ${activeLayerUnit.value}`
      ].join('<br/>')
    }
  },
  grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: false },
  xAxis: { type: 'value', min: -axisMax.value, max: axisMax.value, show: false },
  yAxis: { type: 'value', min: -axisMax.value, max: axisMax.value, show: false },
  visualMap: {
    show: false,
    min: range.value.min,
    max: range.value.max,
    dimension: 2,
    seriesIndex: 0,
    inRange: { color: [...SK_SCALE] }
  },
  series: [
    {
      type: 'scatter',
      symbolSize: layer.value === 'failure' ? 9 : 14,
      itemStyle: layer.value === 'failure' ? { opacity: 0.25 } : {},
      // Measured value printed at each site (hidden on the failure layer, where
      // the dots are context, not readings). Overlapping labels drop out
      // instead of stacking — the tooltip still carries the exact number.
      label: layer.value === 'failure'
        ? { show: false }
        : {
            show: true,
            position: 'top',
            distance: 3,
            fontSize: 10,
            fontFamily: 'monospace',
            color: sk.value.ink,
            formatter: (params) => {
              const v = (params.value as number[])[2]
              if (v == null) return ''
              return layer.value === 'raw' ? v.toFixed(1) : `${v > 0 ? '+' : ''}${v.toFixed(2)}`
            }
          },
      labelLayout: { hideOverlap: true },
      data: points.value.map(p => ({ name: p.chip, value: [p.x, p.y, p.value] }))
    },
    {
      type: 'line', data: waferOutline.value, showSymbol: false, silent: true,
      lineStyle: { color: sk.value.muted, width: 1.25, opacity: 0.55 }, tooltip: { show: false }, z: 0
    },
    {
      type: 'scatter', symbol: 'triangle', symbolSize: 9,
      data: [[0, -waferRadius.value]], itemStyle: { color: sk.value.muted },
      silent: true, z: 1, tooltip: { show: false }
    },
    {
      type: 'line', data: scanPathData.value, showSymbol: false, silent: true,
      lineStyle: { color: sk.value.brand, width: 1, opacity: 0.7, type: 'dashed' as const },
      tooltip: { show: false }, z: 2
    },
    {
      type: 'scatter', symbolSize: 14, data: failurePoints.value,
      itemStyle: { color: 'transparent' },
      label: { show: true, formatter: '✕', color: SK_STATE.bad, fontSize: 13, fontWeight: 'bold' },
      z: 4, tooltip: { show: false }
    },
    {
      type: 'scatter', symbol: 'circle', symbolSize: 22, data: focusPoint.value,
      itemStyle: { color: 'transparent', borderColor: sk.value.series, borderWidth: 3 }, silent: true, z: 5, tooltip: { show: false }
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, {
  onClick: name => emit('focus', name),
  // Sites sit sparsely on the wafer, so the reader points at a location and the
  // nearest site wins. Half a die pitch keeps a click in the empty space
  // between sites — or outside the wafer entirely — from focusing a site the
  // reader was not looking at.
  onGridClick: (detail) => {
    const pitchPx = (props.geo.pitchXmm || 0) / detail.dataPerPixelX
    const chip = nearestPoint(
      points.value.map(p => ({ x: p.x, y: p.y, item: p.chip })),
      detail,
      { maxDistancePx: Math.max(16, pitchPx * 0.75) }
    )
    if (chip) emit('focus', chip)
  }
})
</script>
