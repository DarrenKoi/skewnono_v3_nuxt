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
        <span class="ml-1 font-mono text-[10px] opacity-70">{{ grouped[key]?.length ?? 0 }}</span>
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
            <th class="px-3 py-2 sk-eyebrow">
              Timestamp
            </th>
            <th class="px-3 py-2 sk-eyebrow">
              Ch
            </th>
            <th class="px-3 py-2 sk-eyebrow">
              Judgment
            </th>
            <th class="px-3 py-2 text-right sk-eyebrow">
              Values
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
                class="rounded px-1.5 py-0.5 text-[10px] font-bold"
                :class="row.judgment === 'Conduction'
                  ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
                  : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
              >{{ row.judgment }}</span>
            </td>
            <td class="px-3 py-2 text-right sk-value-num">
              {{ row.values.join(' · ') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SPMVoltages → profile per A/B/C + judgment badge, timestamp-selectable -->
    <div
      v-else-if="activeKey === 'SPMVoltages'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="flex items-center gap-2">
          <span
            v-for="b in spmJudgments"
            :key="b.channel"
            class="rounded bg-(--sk-muted-surface) px-1.5 py-0.5 font-mono text-[10px] font-bold text-(--sk-ink)"
          >{{ b.channel }}: {{ b.judgment }}</span>
        </div>
        <USelect
          v-model="spmTs"
          :items="spmTimestampItems"
          size="xs"
          icon="i-lucide-clock"
          class="w-56"
        />
      </div>
      <div
        ref="chartEl"
        class="h-72 w-full"
      />
    </div>

    <!-- LaserPower → multi-view explorer (원본 / 편차% / Pair 산점도) -->
    <div
      v-else-if="activeKey === 'LaserPower'"
      class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
    >
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2 px-1">
        <span class="sk-title">LaserPower</span>
        <div class="flex overflow-hidden rounded-lg border border-(--sk-border)">
          <button
            v-for="m in laserViews"
            :key="m.value"
            type="button"
            class="px-2.5 py-1 text-[11px] font-semibold transition-colors"
            :class="m.value === laserView
              ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
              : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
            @click="laserView = m.value"
          >
            {{ m.label }}
          </button>
        </div>
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
import { parseFdcValues, type SpmVoltagesValue, type LaserPowerValue, type TemperatureValue } from '~/utils/fdcValues'
import { stableYRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')
const valuesOf = (d: Record<string, unknown>) => (Array.isArray(d.values) ? d.values : [])

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')
const c2 = computed(() => palette.value[2] ?? '#7B6CC4')
const c3 = computed(() => palette.value[3] ?? '#6E7074')

// LaserPower counts reach ~3×10^8; abbreviate axis ticks / tooltips so the
// magnitudes fit the narrow gutters instead of overflowing as raw integers.
const abbr = (v: number): string => {
  if (!Number.isFinite(v)) return '-'
  const a = Math.abs(v)
  if (a >= 1e6) return `${(v / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M`
  if (a >= 1e3) return `${(v / 1e3).toFixed(0)}k`
  return `${v}`
}

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
const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const chartEl = ref<HTMLDivElement | null>(null)

// LaserPower carries four numbers of two scales (two ~0.8 ratios x1/y1, two
// ~10^8 counts x2/y2) whose physical meaning is still unconfirmed, so we offer
// several lenses on the same series rather than commit to one fixed layout.
type LaserView = 'raw' | 'deviation' | 'scatter'
const laserViews: { value: LaserView, label: string }[] = [
  { value: 'raw', label: '원본 · 스케일별' },
  { value: 'deviation', label: '기준선 대비 %' },
  { value: 'scatter', label: 'Pair 산점도' }
]
const laserView = ref<LaserView>('raw')

// --- ContactpinConductionInfo ---
const contactpinRows = computed(() =>
  activeDocs.value.map((d) => {
    const p = parseFdcValues(valuesOf(d))
    const data = p.key === 'ContactpinConductionInfo' ? p.data : null
    return { ts: tsOf(d), channel: data?.channel ?? '', judgment: data?.judgment ?? '', values: data?.values ?? [] }
  })
)

// --- SPMVoltages ---
const spmTimestampItems = computed(() =>
  Array.from(new Set(activeDocs.value.map(tsOf))).filter(Boolean).reverse()
)
const spmTs = ref('')
watch(spmTimestampItems, (items) => {
  if (!items.includes(spmTs.value)) spmTs.value = items[0] ?? ''
}, { immediate: true })
const spmAtTs = computed(() =>
  activeDocs.value
    .filter(d => tsOf(d) === spmTs.value)
    .map(d => parseFdcValues(valuesOf(d)))
    .filter(p => p.key === 'SPMVoltages')
)
const spmJudgments = computed(() =>
  spmAtTs.value.map(p => ({ channel: (p.data as SpmVoltagesValue).channel, judgment: (p.data as SpmVoltagesValue).judgment }))
)

const chartOption = computed<EChartsOption>(() => {
  if (activeKey.value === 'SPMVoltages') {
    const colors = [c0.value, c1.value, c2.value]
    const spmAxis = stableYRange(spmAtTs.value.flatMap(p => (p.data as SpmVoltagesValue).profile)) ?? { scale: true }
    return {
      grid: { left: 48, right: 16, top: 24, bottom: 52 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'category', name: 'index', axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', ...spmAxis, axisLabel: { fontSize: 10 } },
      // Zoom the ~100-point profile — the whole reason SPM needs a range slider.
      dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 16 }],
      series: spmAtTs.value.map((p, i) => ({
        name: (p.data as SpmVoltagesValue).channel,
        type: 'line', smooth: true, showSymbol: false,
        lineStyle: { color: colors[i % colors.length] },
        itemStyle: { color: colors[i % colors.length] },
        data: (p.data as SpmVoltagesValue).profile
      }))
    }
  }

  if (activeKey.value === 'LaserPower') {
    type Ch = 'x1' | 'y1' | 'x2' | 'y2'
    const rows = activeDocs.value.map((d) => {
      const p = parseFdcValues(valuesOf(d))
      const lp = p.key === 'LaserPower' ? (p.data as LaserPowerValue) : null
      return {
        ts: tsOf(d),
        epoch: toEpoch(tsOf(d)),
        x1: lp?.pairs[0]?.x ?? NaN,
        y1: lp?.pairs[0]?.y ?? NaN,
        x2: lp?.pairs[1]?.x ?? NaN,
        y2: lp?.pairs[1]?.y ?? NaN
      }
    })
    const val = (r: (typeof rows)[number], k: Ch) => r[k]
    const timeLine = (k: Ch) => rows.map(r => ({ name: r.ts, value: [r.epoch, val(r, k)] }))

    // --- Deviation %: each channel normalized to its first finite sample, so
    //     all four share one axis and relative drift is comparable across the
    //     scale gap. ---
    if (laserView.value === 'deviation') {
      const pct = (k: Ch) => {
        const base = rows.map(r => val(r, k)).find(Number.isFinite)
        return rows.map(r => ({
          name: r.ts,
          value: [r.epoch, Number.isFinite(val(r, k)) && base ? (val(r, k) / base - 1) * 100 : NaN]
        }))
      }
      return {
        grid: { left: 52, right: 18, top: 28, bottom: 56 },
        tooltip: { trigger: 'axis', valueFormatter: v => Number.isFinite(v as number) ? `${(v as number).toFixed(2)}%` : '-' },
        legend: { top: 2, textStyle: { fontSize: 10 } },
        xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', name: '% vs baseline', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10, formatter: '{value}%' }, scale: true },
        dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 16 }],
        series: [
          { name: 'x1', type: 'scatter', symbol: 'circle', symbolSize: 6, itemStyle: { color: c0.value }, data: pct('x1'), markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: 'rgba(127,127,127,0.55)' }, label: { show: false }, data: [{ yAxis: 0 }] } },
          { name: 'y1', type: 'scatter', symbol: 'triangle', symbolSize: 6, itemStyle: { color: c1.value }, data: pct('y1'), markLine: maintenanceMarkLine.value },
          { name: 'x2', type: 'scatter', symbol: 'circle', symbolSize: 6, itemStyle: { color: c2.value }, data: pct('x2') },
          { name: 'y2', type: 'scatter', symbol: 'triangle', symbolSize: 6, itemStyle: { color: c3.value }, data: pct('y2') }
        ]
      }
    }

    // --- Pair scatter: x vs y within each pair, points colored oldest→newest.
    //     Reveals per-pair correlation/structure the time-series hides. ---
    if (laserView.value === 'scatter') {
      const finiteEpochs = rows.map(r => r.epoch).filter(Number.isFinite)
      const minE = finiteEpochs.length ? Math.min(...finiteEpochs) : 0
      const maxE = finiteEpochs.length ? Math.max(...finiteEpochs) : 1
      const pairPts = (kx: Ch, ky: Ch) => rows
        .filter(r => Number.isFinite(val(r, kx)) && Number.isFinite(val(r, ky)))
        .map(r => ({ name: r.ts, value: [val(r, kx), val(r, ky), r.epoch] }))
      return {
        title: [
          { text: 'pair 1 · x1×y1', left: '26%', top: 6, textAlign: 'center', textStyle: { fontSize: 11, fontWeight: 'normal' } },
          { text: 'pair 2 · x2×y2', left: '77%', top: 6, textAlign: 'center', textStyle: { fontSize: 11, fontWeight: 'normal' } }
        ],
        grid: [
          { left: 52, right: '54%', top: 40, bottom: 40 },
          { left: '52%', right: 62, top: 40, bottom: 40 }
        ],
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            const item = Array.isArray(params) ? params[0] : params
            const d = item?.data as { name: string, value: number[] } | undefined
            return d ? `${d.name}<br/>x ${abbr(d.value[0]!)}<br/>y ${abbr(d.value[1]!)}` : ''
          }
        },
        // Continuous time→color ramp shared by both scatters (older=c1, newer=c0).
        visualMap: {
          type: 'continuous', dimension: 2, min: minE, max: maxE, seriesIndex: [0, 1],
          inRange: { color: [c1.value, c0.value] }, calculable: false, show: false
        },
        xAxis: [
          { type: 'value', gridIndex: 0, name: 'x1', nameLocation: 'middle', nameGap: 22, nameTextStyle: { fontSize: 10 }, scale: true, axisLabel: { fontSize: 9 } },
          { type: 'value', gridIndex: 1, name: 'x2', nameLocation: 'middle', nameGap: 26, nameTextStyle: { fontSize: 10 }, scale: true, axisLabel: { fontSize: 9, formatter: (v: number) => abbr(v) } }
        ],
        yAxis: [
          { type: 'value', gridIndex: 0, name: 'y1', nameTextStyle: { fontSize: 10 }, scale: true, axisLabel: { fontSize: 9 } },
          { type: 'value', gridIndex: 1, name: 'y2', nameTextStyle: { fontSize: 10 }, scale: true, axisLabel: { fontSize: 9, formatter: (v: number) => abbr(v) } }
        ],
        dataZoom: [
          { type: 'inside', xAxisIndex: [0, 1], filterMode: 'none' },
          { type: 'inside', yAxisIndex: [0, 1], filterMode: 'none' }
        ],
        series: [
          { name: 'pair 1', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, symbolSize: 7, data: pairPts('x1', 'y1') },
          { name: 'pair 2', type: 'scatter', xAxisIndex: 1, yAxisIndex: 1, symbolSize: 7, data: pairPts('x2', 'y2') }
        ]
      }
    }

    // --- Raw · by scale (default): ratios (x1,y1) share one axis on top;
    //     counts (x2,y2) get a dual axis below (x2 ≈ 7× y2). All four visible. ---
    const ratioAxis = stableYRange(rows.flatMap(r => [r.x1, r.y1])) ?? { scale: true }
    const x2Axis = stableYRange(rows.map(r => r.x2)) ?? { scale: true }
    const y2Axis = stableYRange(rows.map(r => r.y2)) ?? { scale: true }
    return {
      grid: [
        { left: 58, right: 64, top: '9%', height: '34%' },
        { left: 58, right: 64, top: '57%', height: '30%' }
      ],
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      legend: { top: 2, textStyle: { fontSize: 10 } },
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1] },
        { type: 'slider', xAxisIndex: [0, 1], bottom: 6, height: 16 }
      ],
      xAxis: [
        { type: 'time', gridIndex: 0, axisLabel: { show: false } },
        { type: 'time', gridIndex: 1, axisLabel: { fontSize: 10 } }
      ],
      // Dual count axes hide their splitLines — independent intervals never align.
      yAxis: [
        { type: 'value', gridIndex: 0, name: 'ratio', nameTextStyle: { fontSize: 10 }, ...ratioAxis, axisLabel: { fontSize: 10 } },
        { type: 'value', gridIndex: 1, name: 'x2', position: 'left', nameTextStyle: { fontSize: 10 }, ...x2Axis, axisLabel: { fontSize: 10, formatter: (v: number) => abbr(v) }, splitLine: { show: false } },
        { type: 'value', gridIndex: 1, name: 'y2', position: 'right', nameTextStyle: { fontSize: 10 }, ...y2Axis, axisLabel: { fontSize: 10, formatter: (v: number) => abbr(v) }, splitLine: { show: false } }
      ],
      series: [
        { name: 'x1', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, symbol: 'circle', symbolSize: 6, itemStyle: { color: c0.value }, data: timeLine('x1'), markLine: maintenanceMarkLine.value },
        { name: 'y1', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0, symbol: 'triangle', symbolSize: 6, itemStyle: { color: c1.value }, data: timeLine('y1') },
        { name: 'x2', type: 'scatter', xAxisIndex: 1, yAxisIndex: 1, symbol: 'circle', symbolSize: 6, itemStyle: { color: c2.value }, data: timeLine('x2'), markLine: maintenanceMarkLine.value },
        { name: 'y2', type: 'scatter', xAxisIndex: 1, yAxisIndex: 2, symbol: 'triangle', symbolSize: 6, itemStyle: { color: c3.value }, data: timeLine('y2') }
      ]
    }
  }

  // TemperatureEChuck → one line per position (1/2/3)
  const byPos: Record<string, { ts: string, temp: number }[]> = {}
  for (const d of activeDocs.value) {
    const p = parseFdcValues(valuesOf(d))
    if (p.key !== 'TemperatureEChuck') continue
    const pos = (p.data as TemperatureValue).position
    ;(byPos[pos] ??= []).push({ ts: tsOf(d), temp: (p.data as TemperatureValue).temp })
  }
  const colors = [c0.value, c1.value, c2.value]
  const tempAxis = stableYRange(Object.values(byPos).flat().map(r => r.temp)) ?? { scale: true }
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 52 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '°C', ...tempAxis, axisLabel: { fontSize: 10 } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 16 }],
    series: Object.keys(byPos).sort().map((pos, i) => ({
      name: `pos ${pos}`, type: 'line', showSymbol: true,
      lineStyle: { color: colors[i % colors.length] }, itemStyle: { color: colors[i % colors.length] },
      data: byPos[pos]!.map(r => ({ name: r.ts, value: [toEpoch(r.ts), r.temp] })),
      ...(i === 0 ? { markLine: maintenanceMarkLine.value } : {})
    }))
  }
})

useEchart(chartEl, chartOption)
</script>
