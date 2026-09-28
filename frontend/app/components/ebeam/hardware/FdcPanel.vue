<template>
  <div class="mt-3 space-y-3">
    <!-- fdc_key sub-tabs -->
    <div class="flex overflow-hidden rounded-[10px] border border-(--sk-border) w-fit">
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
      v-if="availableKeys.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
    >
      FDC 데이터가 없습니다.
    </div>

    <!-- ContactpinConductionInfo → status table -->
    <div
      v-else-if="activeKey === 'ContactpinConductionInfo'"
      class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
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
              title="office 확인 2026-09-28 · 중앙값: Conduction 6.4, NonConduction 38.0"
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
            class="border-t border-(--sk-border-soft)"
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
      v-else-if="activeKey === 'SPMVoltages'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="px-1 sk-title">
        채널별 중앙 프로파일 대비 RMS 편차
      </div>
      <div
        ref="spmTrendEl"
        class="h-60 w-full"
      />
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="flex items-center gap-2">
          <span class="sk-label">피팅 모델</span>
          <span
            v-for="b in spmFits"
            :key="b.channel"
            class="rounded bg-(--sk-muted-surface) px-1.5 py-0.5 font-mono text-xs font-bold text-(--sk-ink)"
          >{{ b.channel }} · {{ b.fitModel }}</span>
        </div>
        <USelect
          v-model="spmCycleKey"
          :items="spmCycleItems"
          size="xs"
          icon="i-lucide-clock"
          class="w-72"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </div>

    <!-- LaserPower → stable x1/y1 signals against baseline -->
    <div
      v-else-if="activeKey === 'LaserPower'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-2 px-1 sk-title">
        LaserPower · 기준선 대비 %
      </div>
      <div
        ref="chartEl"
        class="h-[26rem] w-full"
      />
    </div>

    <!-- TemperatureEChuck → trend chart -->
    <div
      v-else
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-1 px-1 sk-title">
        {{ activeKey }} trend
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
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
import { stableYRange, tightYRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

const { palette } = useEchartsTheme()
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
const activeKey = ref('')
watch(availableKeys, (keys) => {
  if (!keys.includes(activeKey.value)) activeKey.value = keys[0] ?? ''
}, { immediate: true })

const activeDocs = computed(() => grouped.value[activeKey.value] ?? [])

const chartEl = ref<HTMLDivElement | null>(null)
const spmTrendEl = ref<HTMLDivElement | null>(null)

// --- ContactpinConductionInfo ---
const contactpinRows = computed(() => deriveContactpinRows(activeDocs.value))

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
const spmFits = computed(() =>
  spmSelected.value.map(p => ({ channel: (p.data as SpmVoltagesValue).channel, fitModel: (p.data as SpmVoltagesValue).fitModel }))
)
const spmDeviations = computed(() => spmDeviationSeries(grouped.value.SPMVoltages ?? []))
// Office 2026-09-28: no scalar separated BM/PM events; this is a deviation trend, not a PM detector.
const spmTrendOption = computed<EChartsOption>(() => ({
  grid: { left: 48, right: 16, top: 24, bottom: 52 },
  tooltip: { trigger: 'axis' },
  legend: { top: 0, textStyle: { fontSize: 10 } },
  xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: 'RMS', scale: true, axisLabel: { fontSize: 10 } },
  dataZoom: sliderZoom(),
  series: spmDeviations.value.map((series, i) => {
    const color = [c0.value, c1.value, c2.value][i % 3]
    return {
      name: series.channel, type: 'line', showSymbol: false,
      lineStyle: { color }, itemStyle: { color },
      data: series.points.map(p => [toEpoch(p.ts), p.value]),
      ...(i === 0 ? { markLine: maintenanceMarkLine.value } : {})
    }
  })
}))
useEchart(spmTrendEl, spmTrendOption)

// Shared chart helpers: one inside+slider zoom pair for single-grid time/index
// charts, and the stable-telemetry range with ECharts' tight auto-fit fallback.
const sliderZoom = (): EChartsOption['dataZoom'] =>
  [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 16 }]
const stableAxis = (values: number[]) => stableYRange(values) ?? { scale: true }

// --- LaserPower: stable x1/y1 baseline deviation ---
type LaserCh = 'x1' | 'y1'
interface LaserRow { ts: string, epoch: number, x1: number, y1: number }
const laserRows = computed<LaserRow[]>(() =>
  activeDocs.value.map((d) => {
    const p = parseFdcValues(valuesOf(d))
    const lp = p.key === 'LaserPower' ? (p.data as LaserPowerValue) : null
    return { ts: tsOf(d), epoch: toEpoch(tsOf(d)), x1: lp?.pairs[0]?.x ?? NaN, y1: lp?.pairs[0]?.y ?? NaN }
  })
)

// Deviation %: each stable channel normalized to its first finite sample.
const laserDeviationOption = (): EChartsOption => {
  const rows = laserRows.value
  const pct = (k: LaserCh) => {
    const base = rows.map(r => r[k]).find(Number.isFinite)
    return rows.map(r => ({
      name: r.ts,
      value: [r.epoch, Number.isFinite(r[k]) && base ? (r[k] / base - 1) * 100 : NaN]
    }))
  }
  return {
    grid: { left: 52, right: 18, top: 28, bottom: 56 },
    tooltip: { trigger: 'axis', valueFormatter: v => Number.isFinite(v as number) ? `${(v as number).toFixed(2)}%` : '-' },
    legend: { top: 2, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '% vs baseline', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10, formatter: '{value}%' }, scale: true, splitLine: { show: false } },
    dataZoom: sliderZoom(),
    series: [
      { name: 'x1', type: 'scatter', symbol: 'circle', symbolSize: 6, itemStyle: { color: c0.value }, data: pct('x1'), markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: 'rgba(127,127,127,0.55)' }, label: { show: false }, data: [{ yAxis: 0 }] } },
      { name: 'y1', type: 'scatter', symbol: 'triangle', symbolSize: 6, itemStyle: { color: c1.value }, data: pct('y1'), markLine: maintenanceMarkLine.value }
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
    tooltip: { trigger: 'axis' },
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

useEchart(chartEl, chartOption)
</script>
