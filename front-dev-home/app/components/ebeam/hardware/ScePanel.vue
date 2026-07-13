<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="!hasSelected"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      SCE 설정 데이터가 없습니다.
    </div>

    <template v-else>
      <!-- Settings compare table: selected vs siblings, diffs flagged -->
      <div class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                Setting
              </th>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                {{ selectedEqp }} (선택)
              </th>
              <th
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]"
              >
                {{ id }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.path"
              class="border-t border-(--sk-border-soft)"
              :class="row.differs ? 'bg-amber-50 dark:bg-amber-950/30' : ''"
            >
              <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
                {{ row.path }}
              </td>
              <td class="px-3 py-2 font-mono font-bold text-(--sk-ink)">
                {{ row.selected !== '' ? row.selected : '-' }}
              </td>
              <td
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono"
                :class="row.siblings[id] !== row.selected ? 'text-(--sk-bad) font-bold' : 'text-(--sk-ink)'"
              >
                {{ row.siblings[id] !== '' ? row.siblings[id] : '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Coefficients[0..359] overlay: values[0] / values[1] in stacked
           per-type panels, selected vs one sibling -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <div class="text-xs font-bold text-(--sk-ink)">
            Coefficients (0–359)
          </div>
          <div class="flex items-center gap-2">
            <UTabs
              v-model="viewMode"
              :items="viewTabs"
              variant="pill"
              size="xs"
            />
            <USelect
              v-model="overlayEqp"
              :items="overlayItems"
              size="xs"
              class="w-44"
            />
          </div>
        </div>
        <div
          ref="chartEl"
          class="h-96 w-full"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { compareSettings, coefficientSeries } from '~/utils/sceCompare'
import { stableRadialRange } from '~/utils/chartRange'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  selectedEqp: string
}>()

const hasSelected = computed(() => Boolean(props.settings[props.selectedEqp]))
const siblingIds = computed(() => Object.keys(props.settings).filter(id => id !== props.selectedEqp).sort())
const rows = computed(() => compareSettings(props.settings, props.selectedEqp))

const overlayItems = computed(() => [
  { label: 'overlay 없음', value: 'none' },
  ...siblingIds.value.map(id => ({ label: id, value: id }))
])
const overlayEqp = ref('none')

const { palette } = useEchartsTheme()
// Overlay uses palette[3]: across the bundled themes it stays hue-distant
// from palette[0], while palette[1]/[2] land on similar or near-background
// tones (e.g. cream/ochre next to the default theme's muted red).
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const cOverlay = computed(() => palette.value[3] ?? '#2F5D8A')

const viewTabs = [
  { label: '라인', value: 'line' },
  { label: '레이더', value: 'radar' }
]
const viewMode = ref('line')

const chartEl = ref<HTMLDivElement | null>(null)
const indices = Array.from({ length: 360 }, (_, i) => i)

interface CoeffPair { v0: number[], v1: number[] }

// values[0] (~±0.02) and values[1] (~0.9–1.0) live on different scales, so a
// shared y-axis flattens both into disjoint bands. Plot each value type in
// its own grid (v0 top, v1 bottom) with a linked x-axis crosshair; the
// selected/overlay pair shares one series name per eqp so each equipment gets
// a single legend entry toggling both panels.
const lineOption = (sel: CoeffPair, sib: CoeffPair | null): EChartsOption => {
  const line = (name: string, data: number[], color: string, gridIndex: number, dashed = false) => ({
    name, type: 'line' as const, showSymbol: false, smooth: false,
    xAxisIndex: gridIndex, yAxisIndex: gridIndex,
    lineStyle: { color, width: 1.2, type: dashed ? ('dashed' as const) : ('solid' as const) },
    itemStyle: { color }, data
  })
  const catAxis = (gridIndex: number, showLabels: boolean) => ({
    type: 'category' as const, gridIndex, data: indices,
    axisLabel: { fontSize: 10, show: showLabels },
    ...(showLabels ? { name: 'index' } : {})
  })
  const valAxis = (gridIndex: number, name: string) => ({
    type: 'value' as const, gridIndex, name, scale: true,
    nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 }
  })
  return {
    grid: [
      { left: 56, right: 16, top: 30, height: '36%' },
      { left: 56, right: 16, bottom: 40, height: '36%' }
    ],
    tooltip: { trigger: 'axis' },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: [catAxis(0, false), catAxis(1, true)],
    yAxis: [valAxis(0, 'values[0]'), valAxis(1, 'values[1]')],
    series: [
      line(props.selectedEqp, sel.v0, c0.value, 0),
      line(props.selectedEqp, sel.v1, c0.value, 1),
      ...(sib
        ? [
            line(overlayEqp.value, sib.v0, cOverlay.value, 0, true),
            line(overlayEqp.value, sib.v1, cOverlay.value, 1, true)
          ]
        : [])
    ]
  }
}

// Radar view: the index IS an angle (0–359°), so each value type gets its own
// polar system (v0 left, v1 right) drawn as a closed 360° profile. A true
// `radar` series would need 360 named indicators — unreadable — so this uses
// line-on-polar. Radius uses stableRadialRange (not tight scaling): a stable
// profile should read as a near-circle, not an exaggerated blob.
const radarOption = (sel: CoeffPair, sib: CoeffPair | null): EChartsOption => {
  const polarLine = (name: string, data: number[], color: string, polarIndex: number, dashed = false) => ({
    name, type: 'line' as const, coordinateSystem: 'polar' as const, polarIndex,
    showSymbol: false, smooth: false,
    lineStyle: { color, width: 1.2, type: dashed ? ('dashed' as const) : ('solid' as const) },
    itemStyle: { color }, data
  })
  const angleAxis = (polarIndex: number) => ({
    polarIndex, type: 'category' as const, data: indices,
    startAngle: 90,
    // 360 categories: label every 45° so the dial stays legible.
    axisLabel: { fontSize: 9, interval: 44 }
  })
  const radiusAxis = (polarIndex: number, values: number[]) => ({
    polarIndex,
    ...(stableRadialRange(values) ?? {}),
    axisLabel: { fontSize: 9 }
  })
  const title = (text: string, left: string) => ({
    text, left, bottom: 4, textAlign: 'center' as const,
    textStyle: { fontSize: 10, fontWeight: 'normal' as const }
  })
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    title: [title('values[0]', '25%'), title('values[1]', '75%')],
    polar: [
      { center: ['25%', '54%'], radius: '66%' },
      { center: ['75%', '54%'], radius: '66%' }
    ],
    angleAxis: [angleAxis(0), angleAxis(1)],
    radiusAxis: [
      radiusAxis(0, [...sel.v0, ...(sib?.v0 ?? [])]),
      radiusAxis(1, [...sel.v1, ...(sib?.v1 ?? [])])
    ],
    series: [
      polarLine(props.selectedEqp, sel.v0, c0.value, 0),
      polarLine(props.selectedEqp, sel.v1, c0.value, 1),
      ...(sib
        ? [
            polarLine(overlayEqp.value, sib.v0, cOverlay.value, 0, true),
            polarLine(overlayEqp.value, sib.v1, cOverlay.value, 1, true)
          ]
        : [])
    ]
  }
}

const chartOption = computed<EChartsOption>(() => {
  const sel = coefficientSeries(props.settings[props.selectedEqp])
  const sib = overlayEqp.value !== 'none' ? coefficientSeries(props.settings[overlayEqp.value]) : null
  return viewMode.value === 'radar' ? radarOption(sel, sib) : lineOption(sel, sib)
})

useEchart(chartEl, chartOption)
</script>
