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

    <!-- TemperatureEchuck / LaserPower → trend chart -->
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
      grid: { left: 48, right: 16, top: 24, bottom: 36 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'category', name: 'index', axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', ...spmAxis, axisLabel: { fontSize: 10 } },
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
    const pts = activeDocs.value.map(d => ({ ts: tsOf(d), parsed: parseFdcValues(valuesOf(d)) }))
    const pairY = (p: (typeof pts)[number], i: number) => (p.parsed.data as LaserPowerValue)?.pairs?.[i]?.x ?? NaN
    const pair = (i: number) => pts.map(p => ({
      name: p.ts,
      value: [toEpoch(p.ts), pairY(p, i)]
    }))
    const pairAxis = (i: number) => stableYRange(pts.map(p => pairY(p, i))) ?? { scale: true }
    return {
      grid: { left: 56, right: 56, top: 24, bottom: 36 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
      // Dual y-axes: hide both splitLine sets — they use independent
      // intervals and never align.
      yAxis: [
        { type: 'value', name: 'pair 1', ...pairAxis(0), axisLabel: { fontSize: 10 }, splitLine: { show: false } },
        { type: 'value', name: 'pair 2', ...pairAxis(1), axisLabel: { fontSize: 10 }, splitLine: { show: false } }
      ],
      series: [
        { name: 'pair 1 (x)', type: 'line', yAxisIndex: 0, lineStyle: { color: c0.value }, itemStyle: { color: c0.value }, data: pair(0), markLine: maintenanceMarkLine.value },
        { name: 'pair 2 (x)', type: 'line', yAxisIndex: 1, lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value }, data: pair(1) }
      ]
    }
  }

  // TemperatureEchuck → one line per position (1/2/3)
  const byPos: Record<string, { ts: string, temp: number }[]> = {}
  for (const d of activeDocs.value) {
    const p = parseFdcValues(valuesOf(d))
    if (p.key !== 'TemperatureEchuck') continue
    const pos = (p.data as TemperatureValue).position
    ;(byPos[pos] ??= []).push({ ts: tsOf(d), temp: (p.data as TemperatureValue).temp })
  }
  const colors = [c0.value, c1.value, c2.value]
  const tempAxis = stableYRange(Object.values(byPos).flat().map(r => r.temp)) ?? { scale: true }
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '°C', ...tempAxis, axisLabel: { fontSize: 10 } },
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
