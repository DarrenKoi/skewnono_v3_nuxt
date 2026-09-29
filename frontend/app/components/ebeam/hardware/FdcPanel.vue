<template>
  <div class="mt-3 space-y-3">
    <div
      role="tablist"
      aria-label="FDC 보기"
      class="flex w-fit overflow-hidden rounded-[var(--sk-r-nav)] border border-(--sk-border)"
    >
      <SkNavPill
        v-for="view in viewOptions"
        :key="view.key"
        role="tab"
        :aria-selected="fdcView === view.key"
        :active="fdcView === view.key"
        :label="view.label"
        size="sm"
        class="!rounded-none !border-0"
        @click="fdcView = view.key"
      />
    </div>

    <EbeamHardwareFdcFleetView
      v-if="fdcView === 'fleet' && (fleetPending || fleet)"
      :fleet="fleet"
      :pending="fleetPending"
      :selected-eqp="selectedEqp"
    />
    <AppEmptyState
      v-else-if="fdcView === 'fleet'"
      title="Fab 전체 FDC 집계가 없습니다."
    />
    <!-- fdc_key sub-tabs -->
    <div
      v-show="fdcView === 'tool'"
      class="flex overflow-hidden rounded-[10px] border border-(--sk-border) w-fit"
    >
      <button
        v-for="key in availableKeys"
        :key="key"
        type="button"
        class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
        :class="key === activeKey
          ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
          : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
        @click="activeKey = key"
      >
        {{ key }}
        <span class="ml-1 font-mono text-xs opacity-70">{{ grouped[key]?.length ?? 0 }}</span>
      </button>
    </div>

    <div
      v-if="fdcView === 'tool' && availableKeys.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
    >
      FDC 데이터가 없습니다.
    </div>

    <!-- ContactpinConductionInfo → status table -->
    <div
      v-else-if="fdcView === 'tool' && activeKey === 'ContactpinConductionInfo'"
      class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
      <p class="px-3 pt-2 sk-meta">
        행을 누르면 그 시점 앞뒤 30분의 측정 recipe 를 봅니다.
      </p>
      <table class="min-w-full text-left text-xs">
        <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
          <tr>
            <th class="px-3 py-2 sk-label">
              Timestamp
            </th>
            <th class="px-3 py-2 sk-label">
              Ch
            </th>
            <th class="px-3 py-2 sk-label">
              Judgment
            </th>
            <th class="px-3 py-2 text-right sk-label">
              Values
            </th>
            <th
              class="px-3 py-2 text-right sk-label"
              title="office 확인 2026-09-28 · 중앙값: Conduction 6.4, NotConduction 38.0"
            >
              범위 (max−min)
            </th>
            <th class="px-3 py-2 text-right sk-label">
              카운터 증가율 (/일)
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in contactpinRows"
            :key="i"
            class="cursor-pointer border-t border-(--sk-border-soft) hover:bg-(--sk-accent-tint) focus-visible:bg-(--sk-accent-tint) focus-visible:outline-none"
            tabindex="0"
            :aria-label="`${row.ts} ${row.channel} ${row.judgment} — 이 시점 측정 recipe 보기`"
            @click="emit('inspect-time', row.ts)"
            @keydown.enter="emit('inspect-time', row.ts)"
          >
            <td class="px-3 py-2 sk-value-num">
              {{ row.ts }}
            </td>
            <td class="px-3 py-2 sk-value-num">
              {{ row.channel }}
            </td>
            <td class="px-3 py-2">
              <span
                class="rounded px-1.5 py-0.5 text-xs font-bold"
                :class="{
                  ok: 'bg-(--sk-ok-soft) text-(--sk-ok)',
                  warn: 'bg-(--sk-warn-soft) text-(--sk-warn)',
                  bad: 'bg-(--sk-bad-soft) text-(--sk-bad)',
                  unknown: 'bg-(--sk-muted-surface) text-(--sk-ink-muted)'
                }[row.state]"
              >{{ row.judgment }}</span>
            </td>
            <td class="px-3 py-2 text-right sk-value-num">
              {{ row.values.map(v => formatFixed(v, 1, '-')).join(' · ') }}
            </td>
            <td class="px-3 py-2 text-right sk-value-num">
              {{ formatFixed(row.spread, 1, '-') }}
            </td>
            <td class="px-3 py-2 text-right sk-value-num">
              {{ formatFixed(row.rate, 1, '-') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SPMVoltages → deviation trend and cycle profile -->
    <div
      v-else-if="fdcView === 'tool' && activeKey === 'SPMVoltages'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="flex flex-wrap items-baseline justify-between gap-2 px-1">
        <span class="sk-title">채널별 중앙 프로파일 대비 RMS 편차</span>
        <span class="sk-meta">차트를 누르면 그 시점의 cycle 이 아래에 표시됩니다 · 툴팁의 버튼으로 그 시점 앞뒤 30분의 측정 recipe 를 봅니다.</span>
      </div>
      <!-- Clicks here only serve the tooltip's inspect button (rendered inside). -->
      <div
        ref="spmTrendEl"
        class="h-60 w-full"
        @click="onInspectClick"
      />
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="flex items-center gap-2">
          <span
            v-if="spmFits.length"
            class="sk-label"
          >피팅 모델</span>
          <span
            v-for="b in spmFits"
            :key="b.channel"
            class="rounded bg-(--sk-muted-surface) px-1.5 py-0.5 font-mono text-xs font-bold text-(--sk-ink)"
          >{{ b.channel }} · {{ b.fitModel }}</span>
        </div>
        <div class="flex items-center gap-2">
          <USelect
            v-model="spmCycleKey"
            :items="spmCycleItems"
            size="xs"
            icon="i-lucide-clock"
            class="w-72"
          />
          <!-- The keyboard path to the same popup as the trend tooltip's button. -->
          <UButton
            v-if="spmCycleKey"
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-list-search"
            label="이 시점 측정 recipe"
            @click="emit('inspect-time', spmCycleKey)"
          />
        </div>
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </div>

    <!-- LaserPower → x1/y1 outliers against the median -->
    <div
      v-else-if="fdcView === 'tool' && activeKey === 'LaserPower'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-2 px-1 sk-title">
        LaserPower · 중앙값 대비 이상치 %
      </div>
      <p class="mb-2 px-1 sk-meta">
        정상 범위(중앙값 ± {{ LASER_OUTLIER_SIGMA }}σ, MAD 추정) 안의 점은 숨기고 벗어난 점만 표시합니다 ·
        x1 이상치 {{ laserStats.x1.points.length }} / 전체 {{ laserStats.x1.total }},
        y1 이상치 {{ laserStats.y1.points.length }} / 전체 {{ laserStats.y1.total }} (유효값 기준)
        <span v-if="laserStats.x1.baseline === 0 || laserStats.y1.baseline === 0"> · 중앙값이 0인 채널은 편차 %를 계산할 수 없습니다.</span>
        · 점을 누르면 그 시점 앞뒤 30분의 측정 recipe 를 봅니다.
      </p>
      <div
        ref="chartEl"
        class="h-[26rem] w-full"
        @click="onInspectClick"
      />
    </div>

    <!-- TemperatureEChuck → trend chart -->
    <div
      v-else-if="fdcView === 'tool'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-1 flex flex-wrap items-baseline justify-between gap-2 px-1">
        <span class="sk-title">{{ activeKey }} trend</span>
        <span
          v-if="activeKey === 'TemperatureEChuck'"
          class="sk-meta"
        >pos 3 은 pos 1 과 같은 값이라 표시하지 않습니다 · 툴팁의 버튼으로 그 시점 앞뒤 30분의 측정 recipe 를 봅니다.</span>
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
        @click="onInspectClick"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import {
  parseFdcValues, contactpinRows as deriveContactpinRows, spmDeviationSeries, fdcDailyMeans,
  fdcDocTs as tsOf, fdcDocValues as valuesOf, fdcEpoch as toEpoch,
  type SpmVoltagesValue, type LaserPowerValue, type TemperatureValue
} from '~/utils/fdcValues'
import { formatFixed } from '~/utils/recipeView'
import { inspectButtonHtml, inspectKeyOf, inspectTooltipBase } from '~/utils/chartInspectTooltip'
import { stableYRange, tightYRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'
import type { FdcFleet } from '~/composables/useHardwareApi'
import { laserOutliers, LASER_OUTLIER_SIGMA, type LaserRow } from '~/utils/fdcLaser'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
  fleet: FdcFleet | null
  fleetPending: boolean
  selectedEqp: string
}>()

// A timestamp the reader wants the measured recipes for (offset-less KST).
const emit = defineEmits<{ 'inspect-time': [at: string] }>()

const fdcView = useState<'tool' | 'fleet'>('hw-fdc-view', () => 'tool')
const viewOptions = [{ key: 'tool', label: '장비' }, { key: 'fleet', label: 'Fab 전체' }] as const

const { palette, surface } = useEchartsTheme()
const c0 = computed(() => palette.value[0]!)
const c1 = computed(() => palette.value[1]!)
const c2 = computed(() => palette.value[2]!)
const c3 = computed(() => palette.value[3]!)

const colorMode = useColorMode()
const maintenanceMarkLine = computed(() =>
  bmPmMarkLine(props.maintenanceEvents ?? [], { dark: colorMode.value === 'dark' })
)

const grouped = computed(() => {
  const g: Record<string, Record<string, unknown>[]> = {}
  for (const d of props.docs) {
    const key = String(d.fdc_key ?? '')
    if (!key) continue
    ;(g[key] ??= []).push(d)
  }
  for (const k of Object.keys(g)) g[k]!.sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
  return g
})
const availableKeys = computed(() => Object.keys(grouped.value).sort())
// Page-scoped like the 장비/Fab 전체 view: a period switch remounts this panel
// (the results area shows a spinner while it refetches), and a local ref would
// drop the reader back on the first sub-tab.
const activeKey = useState('hw-fdc-key', () => '')
watch(availableKeys, (keys) => {
  if (!keys.includes(activeKey.value)) activeKey.value = keys[0] ?? ''
}, { immediate: true })

const activeDocs = computed(() => grouped.value[activeKey.value] ?? [])

const chartEl = ref<HTMLDivElement | null>(null)
const spmTrendEl = ref<HTMLDivElement | null>(null)

// --- ContactpinConductionInfo ---
// Rates need oldest-first order; the table reads newest first.
const contactpinRows = computed(() => deriveContactpinRows(activeDocs.value).reverse())

// --- SPMVoltages ---
// A/B/C are logged a few minutes apart within one measurement cycle, and
// cycles repeat periodically (hours–days apart). Filtering on an exact
// timestamp therefore surfaced only the single channel logged at that instant.
// Cluster docs into cycles (a gap > 30 min starts a new cycle) so one
// selection shows the whole A/B/C set.
const spmCycles = computed(() => {
  const docs = activeDocs.value
    .map(d => ({ ts: tsOf(d), epoch: toEpoch(tsOf(d)), parsed: parseFdcValues(valuesOf(d)) }))
    .filter(d => d.parsed.key === 'SPMVoltages')
    .sort((a, b) => a.epoch - b.epoch)
  const GAP_MS = 30 * 60 * 1000
  const cycles: { key: string, items: typeof docs }[] = []
  let prev = Number.NEGATIVE_INFINITY
  for (const d of docs) {
    const last = cycles[cycles.length - 1]
    if (last && Number.isFinite(d.epoch) && d.epoch - prev < GAP_MS) last.items.push(d)
    else cycles.push({ key: d.ts, items: [d] })
    prev = d.epoch
  }
  return cycles.reverse() // newest cycle first
})
const spmCycleItems = computed(() =>
  spmCycles.value.map(c => ({
    value: c.key,
    label: `${c.key.replace('T', ' ')} · ${c.items.map(i => (i.parsed.data as SpmVoltagesValue).channel).join('/')}`
  }))
)
const spmCycleKey = ref('')
watch(spmCycleItems, (items) => {
  if (!items.some(i => i.value === spmCycleKey.value)) spmCycleKey.value = items[0]?.value ?? ''
}, { immediate: true })
const spmSelected = computed(() => {
  const cycle = spmCycles.value.find(c => c.key === spmCycleKey.value)
  return (cycle?.items ?? [])
    .map(i => i.parsed)
    .filter(p => p.key === 'SPMVoltages')
    .sort((a, b) => (a.data as SpmVoltagesValue).channel.localeCompare((b.data as SpmVoltagesValue).channel))
})
// spline/quartic names describe the fit algorithm, not equipment health.
// CG5000 writes none, so its channels get no badge.
const spmFits = computed(() =>
  spmSelected.value.map(p => ({ channel: (p.data as SpmVoltagesValue).channel, fitModel: (p.data as SpmVoltagesValue).fitModel }))
    .filter(b => b.fitModel)
)
const spmDeviations = computed(() => spmDeviationSeries(grouped.value.SPMVoltages ?? []))
// Office 2026-09-28: no scalar separated BM/PM events; this is a deviation trend, not a PM detector.
// Shared chart helpers: one inside+slider zoom pair for single-grid time/index
// charts, and the stable-telemetry range with ECharts' tight auto-fit fallback.
// Declared before the first option computed: useEchart's watch reads the
// option during setup, so a helper declared below it is a TDZ ReferenceError.
const sliderZoom = (): EChartsOption['dataZoom'] =>
  [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 16 }]
const stableAxis = (values: number[]) => stableYRange(values) ?? { scale: true }

// "이 시점 측정 recipe 보기" in the tooltip (the Sharpness pattern): hovering
// explains a point, the button opens the recipes measured around its time.
// One pinned position per chart host; points carry their doc ts as `name`.
const INSPECT_LABEL = '이 시점 측정 recipe 보기'
const inspectTooltip = (base: ReturnType<typeof inspectTooltipBase>, trigger: 'axis' | 'item', digits: number, unit: string) => ({
  trigger, ...base,
  formatter: (params: unknown) => {
    const items = (Array.isArray(params) ? params : [params]) as { name?: string, marker: string, seriesName: string, value: [number, number] }[]
    const key = items.find(item => item.name)?.name
    const lines = items.map(item => `${item.marker}${escapeHtml(item.seriesName)} <b>${formatFixed(item.value[1], digits, '-')}${unit}</b>`)
    return [key ? escapeHtml(key.replace('T', ' ')) : '', ...lines, key ? inspectButtonHtml(key, INSPECT_LABEL) : ''].filter(Boolean).join('<br/>')
  }
})
const spmTrendTooltip = inspectTooltipBase()
const mainTooltip = inspectTooltipBase()
const onInspectClick = (event: MouseEvent) => {
  const key = inspectKeyOf(event)
  if (key) emit('inspect-time', key)
}

// Clicking the trend picks the cycle nearest the clicked time; the profile
// chart below and the dropdown follow it.
const pickSpmCycleAt = (epoch: number) => {
  let best: { key: string, gap: number } | null = null
  for (const cycle of spmCycles.value) {
    const gap = Math.abs(cycle.items[0]!.epoch - epoch)
    if (!best || gap < best.gap) best = { key: cycle.key, gap }
  }
  if (best) spmCycleKey.value = best.key
}
const spmSelectedEpoch = computed(() => spmCycles.value.find(c => c.key === spmCycleKey.value)?.items[0]?.epoch)

const spmTrendOption = computed<EChartsOption>(() => ({
  grid: { left: 48, right: 16, top: 24, bottom: 52 },
  tooltip: inspectTooltip(spmTrendTooltip, 'axis', 3, ''),
  legend: { top: 0, textStyle: { fontSize: 10 }, data: spmDeviations.value.map(series => series.channel) },
  xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: 'RMS', scale: true, axisLabel: { fontSize: 10 } },
  dataZoom: sliderZoom(),
  series: [
    ...spmDeviations.value.map((series, i) => {
      const color = [c0.value, c1.value, c2.value][i % 3]
      return {
        name: series.channel, type: 'line' as const, showSymbol: false,
        lineStyle: { color }, itemStyle: { color },
        data: series.points.map(p => ({ name: p.ts, value: [toEpoch(p.ts), p.value] })),
        ...(i === 0 ? { markLine: maintenanceMarkLine.value } : {})
      }
    }),
    // Carrier for the selected-cycle marker: series 0 already holds the BM/PM markLine.
    ...(spmSelectedEpoch.value === undefined
      ? []
      : [{
          type: 'line' as const, data: [],
          markLine: {
            silent: true, symbol: 'none', label: { show: false },
            lineStyle: { color: surface.value.ink, type: 'solid' as const, width: 1.5 },
            data: [{ xAxis: spmSelectedEpoch.value }]
          }
        }])
  ]
}))
useEchart(spmTrendEl, spmTrendOption, { onGridClick: ({ x }) => pickSpmCycleAt(x) })

// --- LaserPower: x1/y1 outliers against a robust baseline ---
const laserRows = computed<LaserRow[]>(() =>
  activeDocs.value.map((d) => {
    const p = parseFdcValues(valuesOf(d))
    const lp = p.key === 'LaserPower' ? (p.data as LaserPowerValue) : null
    return { ts: tsOf(d), epoch: toEpoch(tsOf(d)), x1: lp?.pairs[0]?.x ?? NaN, y1: lp?.pairs[0]?.y ?? NaN }
  })
)

const laserStats = computed(() => ({
  x1: laserOutliers(laserRows.value, 'x1'),
  y1: laserOutliers(laserRows.value, 'y1')
}))

// Outliers are few, so the dots can be big click targets (user request
// 2026-09-30: 6px was hard to hit). The triangle gets 2px more to read the same size.
const LASER_SYMBOL = 11
const laserDeviationOption = (): EChartsOption => {
  const { x1, y1 } = laserStats.value
  const times = laserRows.value.map(r => r.epoch).filter(Number.isFinite)
  // Keep the full time window and normal bands visible even without outliers.
  const bandLo = Math.min(x1.band?.lo ?? 0, y1.band?.lo ?? 0)
  const bandHi = Math.max(x1.band?.hi ?? 0, y1.band?.hi ?? 0)
  return {
    grid: { left: 52, right: 18, top: 28, bottom: 56 },
    tooltip: inspectTooltip(mainTooltip, 'item', 2, '%'),
    legend: { top: 2, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', min: times[0], max: times[times.length - 1], axisLabel: { fontSize: 10 } },
    yAxis: {
      type: 'value', name: '중앙값 대비 %', nameTextStyle: { fontSize: 10 },
      // The band-aware min/max land on raw bounds; round the labels they get.
      axisLabel: { fontSize: 10, formatter: (value: number) => `${Number(value.toFixed(2))}%` }, scale: true, splitLine: { show: false },
      min: extent => Math.min(Number.isFinite(extent.min) ? extent.min : 0, bandLo),
      max: extent => Math.max(Number.isFinite(extent.max) ? extent.max : 0, bandHi)
    },
    dataZoom: sliderZoom(),
    series: [
      {
        name: 'x1', type: 'scatter', symbol: 'circle', symbolSize: LASER_SYMBOL, itemStyle: { color: c0.value },
        data: x1.points.map(p => ({ name: p.ts, value: [p.epoch, p.deviation] })),
        markArea: { silent: true, itemStyle: { color: c0.value, opacity: 0.08 }, data: x1.band ? [[{ yAxis: x1.band.lo }, { yAxis: x1.band.hi }]] : [] },
        markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: 'rgba(127,127,127,0.55)' }, label: { show: false }, data: [{ yAxis: 0 }] }
      },
      {
        name: 'y1', type: 'scatter', symbol: 'triangle', symbolSize: LASER_SYMBOL + 2, itemStyle: { color: c1.value },
        data: y1.points.map(p => ({ name: p.ts, value: [p.epoch, p.deviation] })),
        markArea: { silent: true, itemStyle: { color: c1.value, opacity: 0.08 }, data: y1.band ? [[{ yAxis: y1.band.lo }, { yAxis: y1.band.hi }]] : [] },
        markLine: maintenanceMarkLine.value
      }
    ]
  }
}

// TemperatureEChuck parsed once per docs change — up to ~16k docs per 30 days
// at the office — rather than inside chartOption, which also re-runs on every
// theme or BM/PM-marker change.
const tempSeries = computed(() => {
  const byPos: Record<string, { ts: string, epoch: number, temp: number }[]> = {}
  if (activeKey.value !== 'TemperatureEChuck') return { byPos, temps: [], daily: [] }
  for (const d of activeDocs.value) {
    const p = parseFdcValues(valuesOf(d))
    if (p.key !== 'TemperatureEChuck') continue
    const { position, temp } = p.data as TemperatureValue
    // pos 3 repeats pos 1's value (user-confirmed 2026-09-29): drawing it would
    // hide pos 1 and weight it twice in the daily mean.
    if (position === '3') continue
    ;(byPos[position] ??= []).push({ ts: tsOf(d), epoch: toEpoch(tsOf(d)), temp })
  }
  const all = Object.values(byPos).flat()
  const daily = fdcDailyMeans(all.map(r => ({ ts: r.ts, value: r.temp }))).map(p => [toEpoch(p.ts), p.value])
  return { byPos, temps: all.map(r => r.temp), daily }
})

const chartOption = computed<EChartsOption>(() => {
  if (activeKey.value === 'SPMVoltages') {
    const colors = [c0.value, c1.value, c2.value]
    const spmAxis = stableAxis(spmSelected.value.flatMap(p => (p.data as SpmVoltagesValue).profile))
    return {
      grid: { left: 48, right: 16, top: 24, bottom: 52 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'category', name: 'index', axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', ...spmAxis, axisLabel: { fontSize: 10 } },
      // Zoom the ~100-point profile — the whole reason SPM needs a range slider.
      dataZoom: sliderZoom(),
      // One line per channel (A/B/C) in the selected cycle.
      series: spmSelected.value.map((p, i) => ({
        name: (p.data as SpmVoltagesValue).channel,
        type: 'line', smooth: true, showSymbol: false,
        lineStyle: { color: colors[i % colors.length] },
        itemStyle: { color: colors[i % colors.length] },
        data: (p.data as SpmVoltagesValue).profile
      }))
    }
  }

  if (activeKey.value === 'LaserPower') return laserDeviationOption()

  // TemperatureEChuck → one line per position (1/2/3)
  const { byPos, temps, daily } = tempSeries.value
  const colors = [c0.value, c1.value, c2.value]
  // °C is an offset scale, so stableYRange's magnitude-based min span (~5°C
  // around 23) drowns the ~0.6°C of real drift. tightYRange hugs the data
  // (falling through to scale:true when it varies) and only guards the
  // flat-series case, so trend changes stay legible.
  const tempAxis = tightYRange(temps) ?? { scale: true }
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 52 },
    tooltip: inspectTooltip(mainTooltip, 'axis', 2, ' °C'),
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '°C', ...tempAxis, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
    dataZoom: sliderZoom(),
    series: [...Object.keys(byPos).sort().map((pos, i) => ({
      name: `pos ${pos}`, type: 'line' as const, showSymbol: false, sampling: 'lttb' as const,
      lineStyle: { color: colors[i % colors.length], width: 1, opacity: 0.45 }, itemStyle: { color: colors[i % colors.length] },
      data: byPos[pos]!.map(r => ({ name: r.ts, value: [r.epoch, r.temp] })),
      ...(i === 0 ? { markLine: maintenanceMarkLine.value } : {})
    })), {
      name: '일평균', type: 'line', showSymbol: false, sampling: 'lttb',
      // Its own hue: c0..c2 are the three positions, and a bold line in pos 1's
      // color would read as "pos 1, emphasised".
      lineStyle: { color: c3.value, width: 3 }, itemStyle: { color: c3.value },
      data: daily
    }]
  }
})

// LaserPower: a click on a dot opens its recipes straight away - the dots are
// the outliers the reader came for. The other charts open from the tooltip.
useEchart(chartEl, chartOption, {
  onClick: (ts) => {
    if (activeKey.value === 'LaserPower') emit('inspect-time', ts)
  }
})
</script>
