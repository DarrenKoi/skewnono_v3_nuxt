<template>
  <div class="mt-3 space-y-3">
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-(--sk-ink-muted)">Beam Condition</span>
      <USelect
        v-model="beamCondition"
        :items="beamConditionItems"
        size="xs"
        icon="i-lucide-filter"
        class="w-48"
      />
    </div>

    <div class="grid gap-3 lg:grid-cols-2">
      <!-- Center-drift scatter (CenterX vs CenterY, latest emphasized) -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 sk-title">
          Center Drift
        </div>
        <div
          ref="scatterEl"
          class="h-72 w-full"
        />
      </div>
      <!-- Resolution trend: BestReso + ResoIScenter share one axis; gap = ResoDelta -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 sk-title">
          BestReso · ResoIScenter <span class="font-normal text-(--sk-ink-muted)">(gap = ResoDelta)</span>
        </div>
        <div
          ref="trendEl"
          class="h-72 w-full"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { stableYRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}
const fmt = (v: unknown): string => {
  const n = num(v)
  return Number.isFinite(n) ? n.toFixed(2) : '—'
}
const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const colorMode = useColorMode()
const maintenanceMarkLine = computed(() =>
  bmPmMarkLine(props.maintenanceEvents ?? [], { dark: colorMode.value === 'dark' })
)

// One measurement per (timestamp, beam_condition). Merging conditions into one
// timeseries produces a meaningless zig-zag, so the panel always scopes to a
// single beam_condition (default: the first one).
const beamConditions = computed(() =>
  Array.from(new Set(props.docs.map(d => String(d.beam_condition ?? '')).filter(Boolean))).sort()
)
const beamCondition = ref('')
watch(beamConditions, (conds) => {
  if (!conds.includes(beamCondition.value)) beamCondition.value = conds[0] ?? ''
}, { immediate: true })
const beamConditionItems = computed(() => beamConditions.value.map(c => ({ label: c, value: c })))

const ordered = computed(() =>
  props.docs
    .filter(d => String(d.beam_condition ?? '') === beamCondition.value)
    .sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
)

const scatterEl = ref<HTMLDivElement | null>(null)
const trendEl = ref<HTMLDivElement | null>(null)

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const scatterOption = computed<EChartsOption>(() => {
  const pts = ordered.value.map(d => ({ ts: tsOf(d), x: num(d.CenterX), y: num(d.CenterY) }))
  const latest = pts[pts.length - 1]
  const xAxisRange = stableYRange(pts.map(p => p.x)) ?? { scale: true }
  const yAxisRange = stableYRange(pts.map(p => p.y)) ?? { scale: true }
  return {
    grid: { left: 48, right: 16, top: 16, bottom: 36 },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const d = (Array.isArray(params) ? params[0] : params)?.data
        return Array.isArray(d) ? `${d[2]}<br/>X ${d[0]} · Y ${d[1]}` : ''
      }
    },
    xAxis: { type: 'value', name: 'CenterX', ...xAxisRange, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'CenterY', ...yAxisRange, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'scatter', symbolSize: 7, itemStyle: { color: c0.value, opacity: 0.5 },
        data: pts.map(p => [p.x, p.y, p.ts])
      },
      ...(latest
        ? [{
            type: 'scatter' as const, symbolSize: 14,
            itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
            data: [[latest.x, latest.y, `${latest.ts} (latest)`]]
          }]
        : [])
    ]
  }
})

const trendOption = computed<EChartsOption>(() => {
  const rows = ordered.value
  // BestReso and ResoIScenter are the same physical quantity (resolution, nm),
  // so they share one y-axis — the visible vertical gap between them IS
  // ResoDelta. Fit the range over both series together.
  const yRange = stableYRange(rows.flatMap(d => [num(d.BestReso), num(d.ResoIScenter)])) ?? { scale: true }
  const bestData = rows.map(d => [toEpoch(tsOf(d)), num(d.BestReso)])
  const iscData = rows.map(d => [toEpoch(tsOf(d)), num(d.ResoIScenter)])
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      // Both series are in row order, so dataIndex maps straight back to the
      // source doc — read Best / ISCenter / Δ off it rather than off the
      // loosely-typed echarts params.
      formatter: (params) => {
        const arr = Array.isArray(params) ? params : [params]
        const d = rows[arr[0]?.dataIndex ?? -1]
        if (!d) return ''
        return `${tsOf(d)}<br/>Best ${fmt(d.BestReso)} · ISCenter ${fmt(d.ResoIScenter)} · Δ ${fmt(d.ResoDelta)}`
      }
    },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'nm', ...yRange, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: 'BestReso', type: 'line', symbolSize: 5,
        lineStyle: { color: c0.value }, itemStyle: { color: c0.value },
        data: bestData,
        markLine: maintenanceMarkLine.value
      },
      {
        name: 'ResoIScenter', type: 'line', symbolSize: 5,
        lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value },
        data: iscData
      }
    ]
  }
})

useEchart(scatterEl, scatterOption)
useEchart(trendEl, trendOption)
</script>
