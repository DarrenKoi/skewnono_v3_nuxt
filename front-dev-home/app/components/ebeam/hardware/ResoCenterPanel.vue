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
      <span class="ml-auto" />
      <USelect
        v-model="selectedTs"
        :items="timestampItems"
        size="xs"
        icon="i-lucide-clock"
        placeholder="측정 시각 선택"
        class="w-56"
      />
    </div>

    <div class="grid gap-3 lg:grid-cols-2">
      <!-- Center-drift scatter (CenterX vs CenterY, latest emphasized) -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">Center Drift</div>
        <div
          ref="scatterEl"
          class="h-72 w-full"
        />
      </div>
      <!-- BestReso / ResoDelta trend (click → select) -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">BestReso · ResoDelta</div>
        <div
          ref="trendEl"
          class="h-72 w-full"
        />
      </div>
    </div>

    <!-- Focus-sweep curve for the selected measurement (Raw vs Smooth) -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">Focus Sweep (Raw vs Smooth)</div>
      <div
        ref="sweepEl"
        class="h-64 w-full"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'

const props = defineProps<{ docs: Record<string, unknown>[] }>()

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}
const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const beamConditions = computed(() =>
  Array.from(new Set(props.docs.map(d => String(d.beam_condition ?? '')).filter(Boolean))).sort()
)
const beamCondition = ref('all')
const beamConditionItems = computed(() => [
  { label: 'All conditions', value: 'all' },
  ...beamConditions.value.map(c => ({ label: c, value: c }))
])
const filtered = computed(() =>
  beamCondition.value === 'all'
    ? props.docs
    : props.docs.filter(d => String(d.beam_condition ?? '') === beamCondition.value)
)
const ordered = computed(() => [...filtered.value].sort((a, b) => tsOf(a).localeCompare(tsOf(b))))

const timestampItems = computed(() =>
  Array.from(new Set([...ordered.value].map(tsOf).filter(Boolean))).reverse()
)
const selectedTs = ref('')
watch(timestampItems, (items) => {
  if (!items.includes(selectedTs.value)) selectedTs.value = items[0] ?? ''
}, { immediate: true })
const selectedDoc = computed(() => ordered.value.find(d => tsOf(d) === selectedTs.value))

const scatterEl = ref<HTMLDivElement | null>(null)
const trendEl = ref<HTMLDivElement | null>(null)
const sweepEl = ref<HTMLDivElement | null>(null)

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const scatterOption = computed<EChartsOption>(() => {
  const pts = ordered.value.map(d => ({ ts: tsOf(d), x: num(d.CenterX), y: num(d.CenterY) }))
  const latest = pts[pts.length - 1]
  return {
    grid: { left: 48, right: 16, top: 16, bottom: 36 },
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.data[2]}<br/>X ${p.data[0]} · Y ${p.data[1]}` },
    xAxis: { type: 'value', name: 'CenterX', scale: true, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'CenterY', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'scatter', symbolSize: 7, itemStyle: { color: c0.value, opacity: 0.5 },
        data: pts.map(p => [p.x, p.y, p.ts])
      },
      ...(latest ? [{
        type: 'scatter' as const, symbolSize: 14,
        itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
        data: [[latest.x, latest.y, `${latest.ts} (latest)`]]
      }] : [])
    ]
  }
})

const trendOption = computed<EChartsOption>(() => {
  const rows = ordered.value
  return {
    grid: { left: 56, right: 56, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', name: 'BestReso', scale: true, axisLabel: { fontSize: 10 } },
      { type: 'value', name: 'ResoDelta', scale: true, axisLabel: { fontSize: 10 } }
    ],
    series: [
      {
        name: 'BestReso', type: 'line', yAxisIndex: 0,
        lineStyle: { color: c0.value }, itemStyle: { color: c0.value },
        data: rows.map(d => ({ name: tsOf(d), value: [toEpoch(tsOf(d)), num(d.BestReso)], symbolSize: tsOf(d) === selectedTs.value ? 12 : 5 }))
      },
      {
        name: 'ResoDelta', type: 'line', yAxisIndex: 1,
        lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value },
        data: rows.map(d => ({ name: tsOf(d), value: [toEpoch(tsOf(d)), num(d.ResoDelta)], symbolSize: tsOf(d) === selectedTs.value ? 11 : 4 }))
      }
    ]
  }
})

const sweepOption = computed<EChartsOption>(() => {
  const d = selectedDoc.value
  const offsets = Array.isArray(d?.Resolution_Range) ? (d!.Resolution_Range as unknown[]).map(String) : []
  const raw = (d?.Resolution_Range_Raw ?? {}) as Record<string, unknown>
  const smooth = (d?.Resolution_Range_Smooth ?? {}) as Record<string, unknown>
  const lead = (bag: Record<string, unknown>, off: string): number => {
    const a = bag[off]
    return Array.isArray(a) ? num(a[0]) : NaN
  }
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: offsets, name: 'offset', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: 'Raw', type: 'line', smooth: false, lineStyle: { color: c0.value }, itemStyle: { color: c0.value }, data: offsets.map(o => lead(raw, o)) },
      { name: 'Smooth', type: 'line', smooth: true, lineStyle: { color: c1.value }, itemStyle: { color: c1.value }, data: offsets.map(o => lead(smooth, o)) }
    ]
  }
})

useEchart(scatterEl, scatterOption)
useEchart(trendEl, trendOption, { onClick: ts => { selectedTs.value = ts } })
useEchart(sweepEl, sweepOption)
</script>
