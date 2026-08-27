<template>
  <div class="mt-3 space-y-3">
    <!-- Shared comparison-tool picker — governs both sub-tabs -->
    <EbeamHardwareCompareToolPicker
      v-model="compareIds"
      :sibling-ids="siblingIds"
      :selected-eqp="selectedEqp"
      :compare-colors="compareColors"
    />

    <!-- 시계열 | 비교 sub-tabs (same pattern as the FDC fdc_key tabs) -->
    <div class="flex w-fit overflow-hidden rounded-[10px] border border-(--sk-border)">
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
        :class="tab === activeTab
          ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
          : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <!-- ===== 시계열: family chips + trajectory + per-axis trends ===== -->
    <template v-if="activeTab === '시계열'">
      <div
        v-if="families.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
      >
        MDC 이력 데이터가 없습니다.
      </div>
      <template v-else>
        <div class="flex flex-wrap items-center gap-1.5">
          <SkChip
            v-for="fam in families"
            :key="fam.key"
            size="sm"
            :active="fam.key === activeFamilyKey"
            :count="fam.zero.length"
            @click="activeFamilyKey = fam.key"
          >
            {{ fam.key }}
          </SkChip>
        </div>

        <div
          v-if="activeFamily"
          class="grid gap-3"
          :class="isPaired ? 'lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]' : ''"
        >
          <!-- x/y trajectory (paired 0°/90° families only) -->
          <div
            v-if="isPaired"
            class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
          >
            <div class="mb-1 px-1 sk-title">
              0° · 90° Trajectory
            </div>
            <div
              ref="xyEl"
              class="aspect-square w-full"
            />
          </div>

          <!-- per-axis trends -->
          <div class="flex min-w-0 flex-col gap-3">
            <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
              <EbeamHardwareBsmTrendChart
                :label="isPaired ? `${activeFamily.key} · 0°` : activeFamily.key"
                :points="axisPoints(activeFamily.zero)"
                :overlays="overlaysFor('zero')"
                selected=""
                y-mode="tight"
                :events="maintenanceEvents"
              />
            </div>
            <div
              v-if="isPaired"
              class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
            >
              <EbeamHardwareBsmTrendChart
                :label="`${activeFamily.key} · 90°`"
                :points="axisPoints(activeFamily.ninety)"
                :overlays="overlaysFor('ninety')"
                selected=""
                y-mode="tight"
                :events="maintenanceEvents"
              />
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ===== 비교: fleet distribution boxplot per beam condition ===== -->
    <template v-else>
      <div
        v-if="conditions.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
      >
        MDC 설정 데이터가 없습니다.
      </div>
      <div
        v-else
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
      >
        <div class="mb-1 flex items-center justify-between px-1">
          <span class="sk-title">Fleet 분포 · 조건별</span>
          <span class="font-mono text-xs text-(--sk-ink-muted)">
            ◆ {{ selectedEqp || '—' }} · {{ fleetSize }}대
          </span>
        </div>
        <div
          ref="boxEl"
          class="h-80 w-full"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { boxStats } from '~/utils/boxplotStats'
import { tightYRange } from '~/utils/chartRange'
import { buildMdcFamilies, trajectoryPoints, type MdcFamily, type MdcHistoryPoint } from '~/utils/mdcHistory'
import { assignCompareColors, compareBoxPoints } from '~/utils/hardwareCompare'
import type { BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  docs: Record<string, unknown>[]
  // Per-tool MDC history for the picked comparison tools (fetched by
  // HardwareView; empty until those requests resolve).
  compareDocs?: Record<string, Record<string, unknown>[]>
  selectedEqp: string
  maintenanceEvents?: BmPmEvent[]
}>()

const TABS = ['시계열', '비교'] as const
const activeTab = ref<(typeof TABS)[number]>('시계열')

// --- shared comparison selection (page-scoped, shared with SCE) ---
const siblingIds = computed(() => Object.keys(props.settings).filter(id => id !== props.selectedEqp).sort())
const compareIds = useState<string[]>('hw-compare-tools', () => [])
watch(siblingIds, (ids) => {
  const kept = compareIds.value.filter(id => ids.includes(id))
  if (kept.length !== compareIds.value.length) compareIds.value = kept
}, { immediate: true })

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')
const compareColors = computed(() => assignCompareColors(compareIds.value, palette.value))

// --- 시계열 ---
const families = computed(() => buildMdcFamilies(props.docs))
const activeFamilyKey = ref('')
watch(families, (fams) => {
  if (!fams.some(f => f.key === activeFamilyKey.value)) {
    activeFamilyKey.value = (fams.find(f => f.key === '800V_HR') ?? fams[0])?.key ?? ''
  }
}, { immediate: true })
const activeFamily = computed(() => families.value.find(f => f.key === activeFamilyKey.value))
const isPaired = computed(() => (activeFamily.value?.ninety.length ?? 0) > 0)

// BsmTrendChart wants {ts, key, value}; MDC has no per-point selection, so
// the timestamp doubles as the key.
const axisPoints = (pts: MdcHistoryPoint[]) => pts.map(p => ({ ts: p.ts, key: p.ts, value: p.value }))

// Each picked tool's history, keyed by eqp_id, shaped into the same families.
const compareFamilies = computed<Record<string, MdcFamily | undefined>>(() => {
  const out: Record<string, MdcFamily | undefined> = {}
  for (const id of compareIds.value) {
    const fams = buildMdcFamilies(props.compareDocs?.[id] ?? [])
    out[id] = fams.find(f => f.key === activeFamilyKey.value)
  }
  return out
})

// Overlay one thin line per picked tool on the active family's 0°/90° trend.
const overlaysFor = (axis: 'zero' | 'ninety') =>
  compareIds.value
    .map(id => ({
      name: id,
      color: compareColors.value[id],
      points: (compareFamilies.value[id]?.[axis] ?? []).map(p => ({ ts: p.ts, value: p.value }))
    }))
    .filter(o => o.points.length > 0)

const xyEl = ref<HTMLDivElement | null>(null)
const xyOption = computed<EChartsOption>(() => {
  const pts = activeFamily.value ? trajectoryPoints(activeFamily.value) : []
  const n = pts.length
  const latest = pts[n - 1]
  // Each picked tool's trajectory as a low-opacity colored path.
  const compareSeries = compareIds.value.flatMap((id) => {
    const fam = compareFamilies.value[id]
    const cpts = fam ? trajectoryPoints(fam) : []
    if (cpts.length === 0) return []
    return [{
      name: id,
      type: 'scatter' as const,
      symbolSize: 6,
      itemStyle: { color: compareColors.value[id], opacity: 0.55 },
      data: cpts.map(p => ({ value: [p.x, p.y, `${id} · ${p.ts}`] }))
    }]
  })
  const hasCompare = compareSeries.length > 0
  return {
    grid: { left: 56, right: 16, top: hasCompare ? 28 : 16, bottom: 36 },
    ...(hasCompare ? { legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } } } : {}),
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const raw = (Array.isArray(params) ? params[0] : params)?.data as unknown
        const v = (raw as { value?: unknown })?.value ?? raw
        return Array.isArray(v)
          ? (v.length >= 3 ? `${v[2]}<br/>0° ${v[0]} · 90° ${v[1]}` : `0° ${v[0]} · 90° ${v[1]}`)
          : ''
      }
    },
    xAxis: {
      type: 'value',
      name: '0°',
      ...(tightYRange(pts.map(p => p.x)) ?? { scale: true }),
      axisLabel: { fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: '90°',
      ...(tightYRange(pts.map(p => p.y)) ?? { scale: true }),
      axisLabel: { fontSize: 10 }
    },
    series: [
      {
        name: props.selectedEqp,
        type: 'scatter',
        symbolSize: 8,
        // (1.0, 1.0) = no-correction reference crosshair.
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { type: 'dashed', width: 1, color: '#9ca3af', opacity: 0.6 },
          label: { show: false },
          data: [{ xAxis: 1 }, { yAxis: 1 }]
        },
        data: pts.map((p, i) => ({
          value: [p.x, p.y, p.ts],
          // Older → more transparent, so the path reads oldest→newest.
          itemStyle: { color: c0.value, opacity: n <= 1 ? 1 : 0.2 + 0.7 * (i / (n - 1)) }
        }))
      },
      ...compareSeries,
      ...(latest
        ? [{
            name: `${props.selectedEqp} (latest)`,
            type: 'scatter' as const,
            symbolSize: 14,
            itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
            data: [{ value: [latest.x, latest.y, `${latest.ts} (latest)`] }]
          }]
        : [])
    ]
  }
})
useEchart(xyEl, xyOption)

// --- 비교: per-condition fleet distribution + selected + picked-tool markers ---
const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

const fleetSize = computed(() => Object.keys(props.settings).length)

const conditions = computed(() => {
  const set = new Set<string>()
  for (const tool of Object.keys(props.settings)) {
    for (const cond of Object.keys(props.settings[tool] ?? {})) set.add(cond)
  }
  return [...set].sort()
})

const boxRows = computed(() => conditions.value.map((cond) => {
  const fleet = Object.keys(props.settings)
    .map(tool => toNum(props.settings[tool]?.[cond]))
    .filter((v): v is number => v !== null)
  return { cond, stats: boxStats(fleet), mine: toNum(props.settings[props.selectedEqp]?.[cond]) }
}))

// Picked tools mapped to [conditionIndex, value] scatter points (color per tool).
const compareBoxSeries = computed(() => compareBoxPoints(props.settings, compareIds.value, conditions.value))

const boxEl = ref<HTMLDivElement | null>(null)
const fmtVal = (v: number) => v.toFixed(4)
const boxOption = computed<EChartsOption>(() => ({
  grid: { left: 64, right: 16, top: compareIds.value.length ? 28 : 24, bottom: 48 },
  ...(compareIds.value.length ? { legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } } } : {}),
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = Array.isArray(params) ? params[0] : params
      if (!p) return ''
      if (p.seriesType === 'boxplot') {
        const cond = conditions.value[p.dataIndex ?? 0] ?? ''
        // ECharts prepends the category index → normalize to the 5 stats.
        const arr = (p.value ?? p.data) as number[]
        const v = arr.length === 6 ? arr.slice(1) : arr
        return `${cond}<br/>max ${fmtVal(v[4]!)}<br/>Q3 ${fmtVal(v[3]!)}`
          + `<br/>median ${fmtVal(v[2]!)}<br/>Q1 ${fmtVal(v[1]!)}<br/>min ${fmtVal(v[0]!)}`
      }
      const v = p.data as [number, number]
      // Scatter data is null-filtered, so dataIndex is post-filter — the
      // point's own x-index carries the true condition position.
      return `<b>${p.seriesName}</b> · ${conditions.value[v[0]] ?? ''}<br/>${fmtVal(v[1]!)}`
    }
  },
  xAxis: { type: 'category', data: conditions.value, axisLabel: { fontSize: 10, rotate: 20 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  series: [
    {
      name: 'fleet',
      type: 'boxplot',
      itemStyle: { color: 'transparent', borderColor: c0.value },
      boxWidth: ['18%', '42%'],
      data: boxRows.value.map(r => r.stats
        ? [r.stats.min, r.stats.q1, r.stats.median, r.stats.q3, r.stats.max]
        : [NaN, NaN, NaN, NaN, NaN])
    },
    {
      name: props.selectedEqp || 'selected',
      type: 'scatter',
      symbol: 'diamond',
      symbolSize: 12,
      itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
      data: boxRows.value
        .map((r, i) => (r.mine !== null ? [i, r.mine] as [number, number] : null))
        .filter((d): d is [number, number] => d !== null)
    },
    ...compareBoxSeries.value.map(s => ({
      name: s.id,
      type: 'scatter' as const,
      symbol: 'circle' as const,
      symbolSize: 9,
      itemStyle: { color: compareColors.value[s.id], opacity: 0.85 },
      data: s.values
    }))
  ]
}))
useEchart(boxEl, boxOption)
</script>
