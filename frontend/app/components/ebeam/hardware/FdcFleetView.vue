<template>
  <div
    v-if="pending"
    class="rounded-[var(--sk-r-card)] bg-(--sk-muted-surface) px-4 py-6 text-center sk-body"
  >
    fab 전체 FDC 집계를 불러오는 중...
  </div>
  <div
    v-else-if="fleet"
    class="space-y-3"
  >
    <section class="dashboard-surface">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="sk-title">
          Chuck 온도 · fab 비교
        </h3>
        <span class="sk-meta">선택 장비 <strong class="font-mono text-(--sk-ink)">{{ selectedEqp }}</strong></span>
      </div>
      <p class="mt-1 sk-meta">
        장비 간 편차가 장비 내 noise 의 15배라 fab 비교가 의미 있습니다 (office 확인 2026-09-28).
      </p>
      <div
        v-if="heatmap.points.length"
        ref="heatmapEl"
        class="mt-2 h-80 w-full"
      />
      <p
        v-else
        class="mt-4 sk-body"
      >
        온도 데이터가 없습니다.
      </p>
    </section>

    <section class="dashboard-surface">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="sk-title">
          LaserPower x1/y1 순위
        </h3>
        <span class="sk-meta">선택 장비 <strong class="font-mono text-(--sk-ink)">{{ selectedEqp }}</strong></span>
      </div>
      <p class="mt-1 sk-meta">
        x2/y2 는 noise 이므로 제외합니다.
      </p>
      <div
        v-if="laserRows.length"
        ref="laserEl"
        class="mt-2 w-full"
        :style="{ height: `${Math.max(220, laserRows.length * 30 + 70)}px` }"
      />
      <p
        v-else
        class="mt-4 sk-body"
      >
        LaserPower 데이터가 없습니다.
      </p>
    </section>

    <section class="dashboard-surface">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="sk-title">
          Contactpin 판정 비율
        </h3>
        <span class="sk-meta">선택 장비 <strong class="font-mono text-(--sk-ink)">{{ selectedEqp }}</strong></span>
      </div>
      <p class="mt-1 sk-meta">
        판정 건수는 인덱스의 정확한 중복 문서를 제거한 값입니다.
      </p>
      <div
        v-if="pinRows.length"
        ref="pinEl"
        class="mt-2 w-full"
        :style="{ height: `${Math.max(220, pinRows.length * 30 + 70)}px` }"
      />
      <p
        v-else
        class="mt-4 sk-body"
      >
        Contactpin 데이터가 없습니다.
      </p>
    </section>

    <section class="dashboard-surface">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="sk-title">
          Contactpin margin 분포
        </h3>
        <span class="sk-meta">선택 장비 <strong class="font-mono text-(--sk-ink)">{{ selectedEqp }}</strong> · fab 전체 합산</span>
      </div>
      <p class="mt-1 sk-meta">
        점선 영역 15–20: 현장 보고 기준 구간입니다.
      </p>
      <div
        v-if="histogram.bins.length"
        ref="histogramEl"
        class="mt-2 h-64 w-full"
      />
      <p
        v-else
        class="mt-4 sk-body"
      >
        margin 데이터가 없습니다.
      </p>
    </section>

    <section class="dashboard-surface">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="sk-title">
          Counter 증가율
        </h3>
        <span class="sk-meta">원값이 아니라 증가율 (/일) · 선택 장비 <strong class="font-mono text-(--sk-ink)">{{ selectedEqp }}</strong></span>
      </div>
      <div
        v-if="counterRows.length"
        class="mt-2 overflow-x-auto"
      >
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="px-3 py-2 sk-label">
                장비
              </th>
              <th class="px-3 py-2 sk-label">
                채널
              </th>
              <th class="px-3 py-2 text-right sk-label">
                증가율 (/일)
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in counterRows"
              :key="`${row.eqpId}:${row.channel}`"
              class="border-t border-(--sk-border-soft)"
              :class="row.eqpId === selectedEqp ? 'bg-(--sk-accent-tint)' : ''"
            >
              <td
                class="px-3 py-2 font-mono"
                :class="row.eqpId === selectedEqp ? 'border-l-2 border-(--sk-accent) font-bold' : ''"
              >
                {{ row.eqpId }}
              </td>
              <td class="px-3 py-2">
                {{ row.channel }}
              </td>
              <td class="px-3 py-2 text-right sk-value-num">
                {{ formatFixed(row.per_day, 1, '-') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p
        v-else
        class="mt-4 sk-body"
      >
        Counter 데이터가 없습니다.
      </p>
    </section>

    <p class="px-1 sk-meta">
      SPMVoltages 는 장비마다 단위 scale 이 100배까지 달라 fab 비교에서 제외합니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { FdcFleet } from '~/composables/useHardwareApi'
import { formatFixed } from '~/utils/recipeView'
import { SK_SCALE, SK_STATE } from '~/utils/chartPalette'
import { fdcFleetHeatmap, fdcFleetLaserRows, fdcFleetPinRows, fdcFleetHistogram, fdcFleetCounterRows } from '~/utils/fdcFleet'

const props = defineProps<{ fleet: FdcFleet | null, pending: boolean, selectedEqp: string }>()
const { palette, surface } = useEchartsTheme()
// Canvas cannot resolve CSS custom properties: status colors are the fixed
// SK_STATE literals (the same in every theme), ink follows the chart surface.
const colors = computed(() => ({ ink: surface.value.ink, ...SK_STATE }))
const heatmap = computed(() => fdcFleetHeatmap(props.fleet?.tools ?? []))
const laserRows = computed(() => fdcFleetLaserRows(props.fleet?.tools ?? []))
const pinRows = computed(() => fdcFleetPinRows(props.fleet?.tools ?? []))
const histogram = computed(() => fdcFleetHistogram(props.fleet ?? { tools: [], spread_bins: [], spread_bin_width: 1 }))
const counterRows = computed(() => fdcFleetCounterRows(props.fleet?.tools ?? []))

const selectedLabel = (value: string) => value === props.selectedEqp ? `{selected|${value}}` : value
const labelStyle = computed(() => ({ formatter: selectedLabel, rich: { selected: { fontWeight: 'bold' as const, color: colors.value.ink } } }))

const heatmapEl = ref<HTMLDivElement | null>(null)
const heatmapOption = computed<EChartsOption>(() => ({
  grid: { left: 90, right: 95, top: 12, bottom: 55 },
  tooltip: {
    trigger: 'item', renderMode: 'richText',
    formatter: (param: unknown) => {
      const value = (param as { value: [number, number, number] }).value
      return `${heatmap.value.tools[value[1]]} · ${heatmap.value.days[value[0]]}: ${value[2].toFixed(3)} °C`
    }
  },
  xAxis: { type: 'category', data: heatmap.value.days, axisLabel: { fontSize: 10, rotate: 45 } },
  yAxis: { type: 'category', data: heatmap.value.tools, inverse: true, axisLabel: labelStyle.value },
  visualMap: {
    type: 'continuous', min: heatmap.value.min, max: heatmap.value.max === heatmap.value.min ? heatmap.value.max + 0.001 : heatmap.value.max,
    calculable: true, right: 0, top: 'middle', orient: 'vertical', inRange: { color: [...SK_SCALE] }
  },
  series: [{ type: 'heatmap', data: heatmap.value.points, emphasis: { itemStyle: { borderWidth: 2, borderColor: colors.value.ink } } }]
}))
useEchart(heatmapEl, heatmapOption)

const laserEl = ref<HTMLDivElement | null>(null)
const laserOption = computed<EChartsOption>(() => ({
  grid: { left: 90, right: 35, top: 30, bottom: 32 },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: value => formatFixed(value, 3, '-') },
  legend: { top: 0 },
  xAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'category', data: laserRows.value.map(row => row.eqpId), inverse: true, axisLabel: labelStyle.value },
  series: [
    // Dots, not bars: the axis is scaled to the data, and a bar's length on a
    // truncated axis exaggerates small differences.
    { name: 'x1', type: 'scatter', symbolSize: 9, itemStyle: { color: palette.value[0]! }, data: laserRows.value.map(row => row.x1) },
    { name: 'y1', type: 'scatter', symbol: 'triangle', symbolSize: 9, itemStyle: { color: palette.value[1]! }, data: laserRows.value.map(row => row.y1) }
  ]
}))
useEchart(laserEl, laserOption)

const pinEl = ref<HTMLDivElement | null>(null)
const pinOption = computed<EChartsOption>(() => ({
  grid: { left: 90, right: 40, top: 32, bottom: 32 },
  tooltip: {
    trigger: 'axis', renderMode: 'richText', axisPointer: { type: 'shadow' },
    formatter: (params: unknown) => {
      const entries = params as { dataIndex: number }[]
      const row = pinRows.value[entries[0]?.dataIndex ?? -1]
      return row ? `${row.eqpId}\nConduction: ${row.ok}\nUnstableConduction: ${row.warn}\nNonConduction: ${row.bad}` : ''
    }
  },
  legend: { top: 0 },
  xAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
  yAxis: { type: 'category', data: pinRows.value.map(row => row.eqpId), inverse: true, axisLabel: labelStyle.value },
  series: ([
    ['Conduction', 'ok'], ['UnstableConduction', 'warn'], ['NonConduction', 'bad']
  ] as const).map(([name, key]) => ({
    name, type: 'bar' as const, stack: 'total', barMaxWidth: 18,
    itemStyle: { color: colors.value[key] },
    data: pinRows.value.map(row => row.percent[key])
  }))
}))
useEchart(pinEl, pinOption)

const histogramEl = ref<HTMLDivElement | null>(null)
const histogramOption = computed<EChartsOption>(() => ({
  grid: { left: 48, right: 20, top: 32, bottom: 48 },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { top: 0 },
  xAxis: {
    type: 'value', min: histogram.value.bins[0], max: histogram.value.bins.at(-1)! + (props.fleet?.spread_bin_width ?? 1),
    interval: props.fleet?.spread_bin_width ?? 1,
    axisLabel: { fontSize: 10 }
  },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10 } },
  series: histogram.value.series.map((series, index) => ({
    name: series.judgment, type: 'bar' as const, stack: 'total',
    itemStyle: { color: [colors.value.ok, colors.value.warn, colors.value.bad][index] },
    data: series.points,
    ...(index === 0
      ? {
          markArea: {
            silent: true,
            // borderWidth defaults to 0, which hides a border-only band.
            itemStyle: { color: `${SK_STATE.warn}1A`, borderColor: SK_STATE.warn, borderWidth: 1, borderType: 'dashed' as const },
            data: [[{ xAxis: 15 }, { xAxis: 20 }]]
          }
        }
      : {})
  }))
}))
useEchart(histogramEl, histogramOption)
</script>
