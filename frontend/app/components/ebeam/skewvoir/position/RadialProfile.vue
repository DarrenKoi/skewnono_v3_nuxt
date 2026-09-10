<template>
  <EbeamSkewvoirPanelFrame
    title="Radial Profile"
    :meta="meta"
    icon="i-lucide-line-chart"
    body-class="flex flex-col gap-2"
  >
    <template v-if="bins.length">
      <div
        ref="chartEl"
        role="img"
        class="h-40 w-full shrink-0"
        :aria-label="ariaLabel"
      />
      <span class="sr-only">{{ ariaLabel }}</span>
      <div class="min-h-0 overflow-auto">
        <table class="w-full border-collapse text-xs">
          <thead class="sticky top-0 bg-(--sk-surface)">
            <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
              <th
                scope="col"
                class="px-1.5 py-1 text-left font-semibold"
              >
                R (mm)
              </th>
              <th
                scope="col"
                class="px-1.5 py-1 text-right font-semibold"
              >
                median
              </th>
              <th
                scope="col"
                class="px-1.5 py-1 text-right font-semibold"
              >
                IQR
              </th>
              <th
                scope="col"
                class="px-1.5 py-1 text-right font-semibold"
              >
                N
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(b, i) in bins"
              :key="i"
              class="border-b border-(--sk-border-soft) last:border-0"
            >
              <td class="px-1.5 py-1 font-mono tabular-nums">
                {{ b.radiusMm.toFixed(1) }}
              </td>
              <td class="px-1.5 py-1 text-right font-mono tabular-nums">
                {{ b.median.toFixed(3) }}
              </td>
              <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink-muted)">
                {{ b.spread.toFixed(3) }}
              </td>
              <td class="px-1.5 py-1 text-right font-mono tabular-nums">
                {{ b.count }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <div
      v-else
      class="flex flex-1 items-center justify-center px-4 text-center sk-body"
    >
      {{ spatial.readiness.coordinates === 'unavailable' ? '평가 불가 — 좌표 정보가 없습니다.' : '방사형 프로파일을 만들 측정점이 없습니다.' }}
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { SpatialResult } from '~/utils/skewvoirAnalysis/spatial'

const props = defineProps<{
  spatial: SpatialResult
  parameter: string
  unit: string
}>()

const sk = useChartPalette()

const bins = computed(() => props.spatial.radiusBins)

// Explicit y window over everything the chart draws (median line + IQR band),
// padded so the profile sits in the middle of the plot instead of riding the
// frame — `scale: true` alone still lets the extreme bins touch the edges.
const yExtent = computed(() => {
  const values = bins.value.flatMap(b => [b.median, b.q1, b.q3]).filter(v => Number.isFinite(v))
  if (values.length === 0) return null
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  // 15% headroom each side; a flat profile still gets a visible window.
  const pad = (hi - lo) * 0.15 || Math.max(Math.abs(hi) * 0.05, 0.5)
  return { min: lo - pad, max: hi + pad }
})

const meta = computed(() => `${bins.value.length} bins · ${props.unit || props.parameter}`)

// Screen-reader text alternative for the canvas chart: bin count plus the
// center → outer median, the headline numbers the plot exists to show.
const ariaLabel = computed(() => {
  const u = props.unit || props.parameter
  if (!bins.value.length) return '방사형 프로파일: 표시할 데이터가 없습니다.'
  const first = bins.value[0]!
  const last = bins.value[bins.value.length - 1]!
  return `방사형 프로파일: ${bins.value.length}개 반경 구간, 중심 ${first.median.toFixed(1)}${u} → 외곽 ${last.median.toFixed(1)}${u}`
})

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const arr = params as { data?: number[] }[]
      const p = arr[0]?.data
      if (!p) return ''
      const bin = bins.value.find(b => b.radiusMm === p[0])
      if (!bin) return ''
      return [
        `r ${bin.radiusMm.toFixed(1)} mm · N=${bin.count}`,
        `median <b>${bin.median.toFixed(3)}</b> ${props.unit}`,
        `IQR ${bin.spread.toFixed(3)} ${props.unit}`
      ].join('<br/>')
    }
  },
  grid: { left: 48, right: 16, top: 14, bottom: 30, containLabel: true },
  xAxis: {
    type: 'value',
    name: 'distance from center (mm)',
    nameLocation: 'middle',
    nameGap: 22,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    min: yExtent.value?.min,
    max: yExtent.value?.max,
    name: props.unit || props.parameter,
    nameTextStyle: { fontSize: 10 },
    axisLabel: { fontSize: 10, formatter: (value: number) => value.toFixed(2) }
  },
  series: [
    // IQR band via stacked transparent lower + filled span.
    {
      type: 'line', stack: 'iqr', symbol: 'none', silent: true, tooltip: { show: false },
      lineStyle: { opacity: 0 }, data: bins.value.map(b => [b.radiusMm, b.q1]), z: 1
    },
    {
      type: 'line', stack: 'iqr', symbol: 'none', silent: true, tooltip: { show: false },
      lineStyle: { opacity: 0 }, areaStyle: { color: sk.value.sand, opacity: 0.35 },
      data: bins.value.map(b => [b.radiusMm, b.q3 - b.q1]), z: 1
    },
    {
      type: 'line', name: 'median', symbolSize: 6, showSymbol: true,
      lineStyle: { color: sk.value.series, width: 2 }, itemStyle: { color: sk.value.series },
      data: bins.value.map(b => [b.radiusMm, b.median]), z: 3
    }
  ]
}))

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option)
</script>
