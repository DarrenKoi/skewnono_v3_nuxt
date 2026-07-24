<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="!hasSelected && docs.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
    >
      SCE 설정 데이터가 없습니다. (R3/R4 등 일부 fab은 SCE를 사용하지 않습니다)
    </div>

    <template v-else>
      <!-- 비교 | 시계열 sub-tabs (same pattern as the MDC tabs) -->
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

      <!-- ===== 시계열: bidaily archive — param trend + coefficient evolution ===== -->
      <template v-if="activeTab === '시계열'">
        <div
          v-if="docs.length === 0"
          class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
        >
          SCE 이력 데이터가 없습니다.
        </div>
        <template v-else>
          <div class="space-y-1.5">
            <div
              v-for="group in trendGroups"
              :key="group.block"
              class="flex flex-wrap items-center gap-1.5"
            >
              <span class="w-[4.5rem] shrink-0 sk-eyebrow text-(--sk-ink-muted)">
                {{ group.block }}
              </span>
              <SkChip
                v-for="k in group.keys"
                :key="k.key"
                size="sm"
                :active="k.key === activeParamKey"
                @click="activeParamKey = k.key"
              >
                {{ k.label }}
              </SkChip>
            </div>
          </div>

          <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
            <EbeamHardwareBsmTrendChart
              :label="`${sceParamLabel(activeParamKey)} · ${selectedEqp}`"
              :points="paramPoints"
              selected=""
              y-mode="tight"
              :events="maintenanceEvents"
            />
          </div>

          <!-- One coefficient index tracked over the collection dates -->
          <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
            <div class="mb-1 flex flex-wrap items-center justify-between gap-2 px-1">
              <div class="sk-title">
                Coefficient 추세 · index {{ coeffIndex }}
              </div>
              <div class="flex items-center gap-2">
                <input
                  :value="coeffIndex"
                  type="range"
                  min="0"
                  max="359"
                  step="1"
                  class="w-40 accent-(--sk-accent)"
                  aria-label="Coefficient index"
                  @input="setCoeffIndex(($event.target as HTMLInputElement).value)"
                >
                <input
                  :value="coeffIndex"
                  type="number"
                  min="0"
                  max="359"
                  class="w-16 rounded-md border border-(--sk-border) bg-(--sk-surface) px-1.5 py-0.5 text-right font-mono text-[11px] text-(--sk-ink)"
                  aria-label="Coefficient index (number)"
                  @change="setCoeffIndex(($event.target as HTMLInputElement).value)"
                >
              </div>
            </div>
            <div
              ref="coeffTrendEl"
              class="h-64 w-full"
            />
          </div>

          <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
            <div class="mb-1 flex flex-wrap items-center justify-between gap-2 px-1">
              <div class="sk-title">
                Coefficients 변화 (0–359) · 설정 버전별
                <span class="font-normal text-(--sk-ink-muted)">— 클릭하면 해당 index 추세로</span>
              </div>
              <div class="flex flex-wrap items-center gap-1.5">
                <span class="font-mono text-[11px] text-(--sk-ink-muted) tabular-nums">
                  {{ evolutionDates.length }}회 수집 · {{ revisions.length }}개 버전
                </span>
                <USelectMenu
                  v-model="selectedRevisions"
                  v-model:open="revisionMenuOpen"
                  multiple
                  value-key="value"
                  :items="revisionItems"
                  :search-input="{ placeholder: '수집일 검색…' }"
                  placeholder="버전 선택"
                  icon="i-lucide-calendar-days"
                  size="xs"
                  class="min-w-[15rem]"
                  :ui="{ itemTrailingIcon: 'hidden' }"
                >
                  <template #default>
                    <span class="truncate">
                      {{ selectedRevisions.length > 0 ? `버전 ${selectedRevisions.length}/${revisions.length}개` : '버전 선택' }}
                    </span>
                  </template>
                  <template #item-leading="{ item }">
                    <span
                      class="flex h-4 w-4 items-center justify-center rounded border"
                      :class="selectedRevisions.includes(item.value)
                        ? 'border-(--sk-ink) bg-(--sk-ink) text-white dark:text-zinc-900'
                        : 'border-(--sk-border)'"
                    >
                      <UIcon
                        v-if="selectedRevisions.includes(item.value)"
                        name="i-lucide-check"
                        class="h-3 w-3"
                      />
                    </span>
                  </template>
                  <!-- Same explicit close affordance as the 비교 장비 picker
                       (click-outside / Esc also close the menu). -->
                  <template #content-bottom>
                    <div class="border-t border-(--sk-border-soft) p-1">
                      <UButton
                        block
                        size="xs"
                        color="neutral"
                        variant="soft"
                        icon="i-lucide-check"
                        @click="revisionMenuOpen = false"
                      >
                        닫기
                      </UButton>
                    </div>
                  </template>
                </USelectMenu>
                <!-- The way back from 전체 on a window with many re-tunes. -->
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  @click="selectedRevisions = sceLatestDates(revisionKeys, DEFAULT_REVISIONS)"
                >
                  최근 {{ DEFAULT_REVISIONS }}개
                </UButton>
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  :disabled="selectedRevisions.length === revisions.length"
                  @click="selectedRevisions = [...revisionKeys]"
                >
                  전체
                </UButton>
              </div>
            </div>
            <div
              v-if="selectedRevisions.length === 0"
              class="flex h-96 w-full items-center justify-center text-center sk-body"
            >
              비교할 설정 버전을 선택하세요.
            </div>
            <div
              v-else
              ref="evolutionEl"
              class="h-96 w-full"
            />
          </div>
        </template>
      </template>

      <!-- ===== 비교: latest snapshot — settings table + curve overlay ===== -->
      <div
        v-else-if="!hasSelected"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center sk-body ring-1 ring-(--sk-border-soft)"
      >
        SCE 설정 데이터가 없습니다. (R3/R4 등 일부 fab은 SCE를 사용하지 않습니다)
      </div>
      <template v-else>
        <!-- Shared comparison-tool picker (drives both the table and the curve) -->
        <EbeamHardwareCompareToolPicker
          v-model="compareIds"
          :sibling-ids="siblingIds"
          :selected-eqp="selectedEqp"
        />

        <!-- Settings compare table: selected vs picked tools, diffs flagged -->
        <div class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
          <table class="min-w-full text-left text-xs">
            <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
              <tr>
                <th class="px-3 py-2 sk-eyebrow">
                  Setting
                </th>
                <th class="px-3 py-2 sk-eyebrow">
                  {{ selectedEqp }} (선택)
                </th>
                <th
                  v-for="id in compareIds"
                  :key="id"
                  class="px-3 py-2 sk-eyebrow"
                >
                  <span class="inline-flex items-center gap-1.5">
                    <span
                      class="h-2 w-2 rounded-full"
                      :style="{ background: compareColors[id] }"
                    />
                    {{ id }}
                  </span>
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
                  v-for="id in compareIds"
                  :key="id"
                  class="px-3 py-2 font-mono"
                  :class="row.siblings[id] !== row.selected ? 'text-(--sk-bad) font-bold' : 'text-(--sk-ink)'"
                >
                  {{ row.siblings[id] !== '' && row.siblings[id] !== undefined ? row.siblings[id] : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
          <p
            v-if="compareIds.length === 0"
            class="border-t border-(--sk-border-soft) px-3 py-3 text-center sk-body"
          >
            위 드롭박스에서 비교할 장비를 선택하면 열이 추가됩니다.
          </p>
        </div>

        <!-- Coefficients[0..359] overlay: values[0] / values[1] in stacked
             per-type panels, selected vs every picked tool -->
        <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
          <div class="mb-1 flex items-center justify-between gap-2 px-1">
            <div class="sk-title">
              Coefficients (0–359)
            </div>
            <UTabs
              v-model="viewMode"
              :items="viewTabs"
              variant="pill"
              size="xs"
            />
          </div>
          <div
            ref="chartEl"
            class="h-96 w-full"
          />
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { compareSettings, coefficientSeries } from '~/utils/sceCompare'
import {
  sceCoeffIndexSeries, sceCoeffRevisions, sceDocDates, sceLatestDates, sceParamLabel,
  sceParamSeries, sceRevisionLabel, sceTrendKeys,
  type SceCoeffRevision, type SceTrendKey
} from '~/utils/sceHistory'
import { assignCompareColors, assignSeriesColors } from '~/utils/hardwareCompare'
import { stableRadialRange } from '~/utils/chartRange'
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  // Bidaily archive snapshots of the selected tool ({date, ...blocks}, asc).
  docs?: Record<string, unknown>[]
  selectedEqp: string
  maintenanceEvents?: BmPmEvent[]
}>()

const TABS = ['비교', '시계열'] as const
const activeTab = ref<(typeof TABS)[number]>('비교')

const docs = computed(() => props.docs ?? [])
const maintenanceEvents = computed(() => props.maintenanceEvents ?? [])

const hasSelected = computed(() => Boolean(props.settings[props.selectedEqp]))
const siblingIds = computed(() => Object.keys(props.settings).filter(id => id !== props.selectedEqp).sort())

// --- 시계열: setting-param trend (SCEParam / SemCond / ImgCond) ---
const trendKeys = computed(() => sceTrendKeys(docs.value))
const activeParamKey = ref('')
watch(trendKeys, (keys) => {
  if (!keys.some(k => k.key === activeParamKey.value)) activeParamKey.value = keys[0]?.key ?? ''
}, { immediate: true })
const paramPoints = computed(() => sceParamSeries(docs.value, activeParamKey.value))

// Chip strip grouped by block. sceTrendKeys already orders block-then-key, so
// one pass collects each run of a block into its own group.
const trendGroups = computed(() => {
  const groups: { block: string, keys: SceTrendKey[] }[] = []
  for (const k of trendKeys.value) {
    const last = groups[groups.length - 1]
    if (last && last.block === k.block) last.keys.push(k)
    else groups.push({ block: k.block, keys: [k] })
  }
  return groups
})

// --- 시계열: coefficient trend at one index ---
// The evolution chart below shows every index at once; this tracks a single
// index over the collection dates. Clicking the evolution chart sets it.
const coeffIndex = ref(0)
const setCoeffIndex = (v: number | string) => {
  const n = Math.round(Number(v))
  coeffIndex.value = Number.isFinite(n) ? Math.min(359, Math.max(0, n)) : 0
}
const coeffTrendEl = ref<HTMLDivElement | null>(null)
const coeffPoints = computed(() => sceCoeffIndexSeries(docs.value, coeffIndex.value))

// Page-scoped selection shared with the MDC panel (see HardwareView). Prune to
// the current cohort so a stale id from a previous tool never lingers.
const compareIds = useState<string[]>('hw-compare-tools', () => [])
watch(siblingIds, (ids) => {
  const kept = compareIds.value.filter(id => ids.includes(id))
  if (kept.length !== compareIds.value.length) compareIds.value = kept
}, { immediate: true })

const rows = computed(() => compareSettings(props.settings, props.selectedEqp, compareIds.value))

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const colorMode = useColorMode()
const maintenanceMarkLine = computed(() =>
  bmPmMarkLine(maintenanceEvents.value, { dark: colorMode.value === 'dark' })
)
// One stable color per picked tool, reused by the table dots and the curves.
const compareColors = computed(() => assignCompareColors(compareIds.value, palette.value))

const viewTabs = [
  { label: '라인', value: 'line' },
  { label: '레이더', value: 'radar' }
]
const viewMode = ref('line')

const chartEl = ref<HTMLDivElement | null>(null)
const indices = Array.from({ length: 360 }, (_, i) => i)

interface CoeffPair { v0: number[], v1: number[] }
interface CompareCoeff { id: string, pair: CoeffPair, color: string }

// values[0] (~±0.02) and values[1] (~0.9–1.0) live on different scales, so a
// shared y-axis flattens both into disjoint bands. Plot each value type in
// its own grid (v0 top, v1 bottom) with a linked x-axis crosshair; the
// selected/picked tools share one series name per eqp so each equipment gets
// a single legend entry toggling both panels.
const lineOption = (sel: CoeffPair, cmp: CompareCoeff[]): EChartsOption => {
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
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    xAxis: [catAxis(0, false), catAxis(1, true)],
    yAxis: [valAxis(0, 'values[0]'), valAxis(1, 'values[1]')],
    series: [
      line(props.selectedEqp, sel.v0, c0.value, 0),
      line(props.selectedEqp, sel.v1, c0.value, 1),
      ...cmp.flatMap(c => [
        line(c.id, c.pair.v0, c.color, 0, true),
        line(c.id, c.pair.v1, c.color, 1, true)
      ])
    ]
  }
}

// Radar view: the index IS an angle (0–359°), so each value type gets its own
// polar system (v0 left, v1 right) drawn as a closed 360° profile. A true
// `radar` series would need 360 named indicators — unreadable — so this uses
// line-on-polar. Radius uses stableRadialRange (not tight scaling): a stable
// profile should read as a near-circle, not an exaggerated blob.
const radarOption = (sel: CoeffPair, cmp: CompareCoeff[]): EChartsOption => {
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
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    title: [title('values[0]', '25%'), title('values[1]', '75%')],
    polar: [
      { center: ['25%', '54%'], radius: '66%' },
      { center: ['75%', '54%'], radius: '66%' }
    ],
    angleAxis: [angleAxis(0), angleAxis(1)],
    radiusAxis: [
      radiusAxis(0, [...sel.v0, ...cmp.flatMap(c => c.pair.v0)]),
      radiusAxis(1, [...sel.v1, ...cmp.flatMap(c => c.pair.v1)])
    ],
    series: [
      polarLine(props.selectedEqp, sel.v0, c0.value, 0),
      polarLine(props.selectedEqp, sel.v1, c0.value, 1),
      ...cmp.flatMap(c => [
        polarLine(c.id, c.pair.v0, c.color, 0, true),
        polarLine(c.id, c.pair.v1, c.color, 1, true)
      ])
    ]
  }
}

const chartOption = computed<EChartsOption>(() => {
  const sel = coefficientSeries(props.settings[props.selectedEqp])
  const cmp: CompareCoeff[] = compareIds.value.map(id => ({
    id,
    pair: coefficientSeries(props.settings[id]),
    color: compareColors.value[id] ?? '#2F5D8A'
  }))
  return viewMode.value === 'radar' ? radarOption(sel, cmp) : lineOption(sel, cmp)
})

useEchart(chartEl, chartOption)

// One index's two values across the collection dates. values[0] (~±0.02) and
// values[1] (~0.9–1.0) sit on different scales, so each gets its own axis;
// their ticks never align, hence no split lines. `scale: true` rather than
// stableYRange — at this magnitude the drift IS the signal (same reasoning as
// BsmTrendChart's 'tight' mode).
const coeffTrendOption = computed<EChartsOption>(() => {
  const { v0, v1 } = coeffPoints.value
  const epoch = (ts: string) => new Date(ts).getTime()
  const axis = (name: string) => ({
    type: 'value' as const, name, scale: true,
    nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 },
    splitLine: { show: false }
  })
  return {
    grid: { left: 64, right: 64, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: [axis('values[0]'), axis('values[1]')],
    series: [
      {
        name: 'values[0]', type: 'line', yAxisIndex: 0, symbolSize: 5,
        lineStyle: { color: c0.value }, itemStyle: { color: c0.value },
        data: v0.map(p => [epoch(p.ts), p.value]),
        markLine: maintenanceMarkLine.value
      },
      {
        name: 'values[1]', type: 'line', yAxisIndex: 1, symbolSize: 5,
        lineStyle: { color: c1.value, type: 'dashed' }, itemStyle: { color: c1.value },
        data: v1.map(p => [epoch(p.ts), p.value])
      }
    ]
  }
})
useEchart(coeffTrendEl, coeffTrendOption)

// --- 시계열: coefficient-curve evolution ---
// One curve per PICKED settings REVISION, in the same v0/v1 stacked grids as
// the compare view. Two problems forced this shape:
//   1. SCE is re-tuned at PM, not per collection, so a window of ~16 bidaily
//      docs is typically 2-3 distinct curves — the rest draw the same line on
//      top of itself. sceCoeffRevisions collapses each run of identical curves
//      into one entry carrying its date span.
//   2. Even across distinct curves, a same-hue opacity ramp says "older",
//      never "which one". Each picked revision gets its own color + legend
//      entry instead.
// The default is the newest few revisions.
const DEFAULT_REVISIONS = 3
const evolutionDates = computed(() => sceDocDates(docs.value))
const revisions = computed(() => sceCoeffRevisions(docs.value))
// A revision is identified by its FIRST date — stable across re-fetches, and
// already the label's leading text.
const revisionKeys = computed(() => revisions.value.map(r => r.date))
// Newest first in the menu — recent re-tunes are what a reader reaches for.
const revisionItems = computed(() =>
  [...revisions.value].reverse().map(r => ({ label: sceRevisionLabel(r), value: r.date }))
)
const selectedRevisions = ref<string[]>([])
// Controlled open state so the 닫기 button can close the menu; Esc and
// outside-click still work because Reka emits update:open through this binding.
const revisionMenuOpen = ref(false)
watch(revisionKeys, (keys) => {
  // Keep whatever the reader picked that still exists in the new window, and
  // re-seed to the newest few only when nothing carried over (first load, or a
  // tool/range switch that replaced the window wholesale).
  const kept = selectedRevisions.value.filter(d => keys.includes(d))
  selectedRevisions.value = kept.length > 0 ? kept : sceLatestDates(keys, DEFAULT_REVISIONS)
}, { immediate: true })

// Every doc in a revision carries the same curve by construction, so the
// revision's first doc is a complete stand-in for the run. Filtering in
// revision order keeps the draw order ascending no matter what order the boxes
// were ticked in, so the newest curve is always drawn last — i.e. on top.
const evolutionSeries = computed(() => {
  const picked = new Set(selectedRevisions.value)
  const byDate = new Map(docs.value.filter(d => typeof d.date === 'string').map(d => [String(d.date), d]))
  return revisions.value
    .filter(r => picked.has(r.date))
    .map(r => ({ rev: r, doc: byDate.get(r.date) }))
    .filter((s): s is { rev: SceCoeffRevision, doc: Record<string, unknown> } => Boolean(s.doc))
})
// Newest gets palette[0] — it is the curve the others are read against, so it
// wears the primary accent, the same color the selected tool has in 비교.
const evolutionColors = computed(() =>
  assignSeriesColors(evolutionSeries.value.map(s => s.rev.date).reverse(), palette.value)
)

const evolutionEl = ref<HTMLDivElement | null>(null)
const evolutionOption = computed<EChartsOption>(() => {
  const picked = evolutionSeries.value
  const line = (name: string, data: number[], color: string, latest: boolean, gridIndex: number) => ({
    name, type: 'line' as const, showSymbol: false, smooth: false,
    xAxisIndex: gridIndex, yAxisIndex: gridIndex,
    lineStyle: { color, width: latest ? 1.8 : 1.2 },
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
    // Both panels' series share one name per revision, so each revision is a
    // single legend entry that toggles its v0 and v1 curves together.
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    xAxis: [catAxis(0, false), catAxis(1, true)],
    yAxis: [valAxis(0, 'values[0]'), valAxis(1, 'values[1]')],
    series: picked.flatMap(({ rev, doc }, i) => {
      const pair = coefficientSeries(doc)
      // The legend has to fit several of these, so it carries the span without
      // the 회 count the menu shows.
      const name = rev.dates.length > 1 ? `${rev.date} ~ ${rev.through.slice(5)}` : rev.date
      const color = evolutionColors.value[rev.date] ?? c0.value
      const latest = i === picked.length - 1
      return [line(name, pair.v0, color, latest, 0), line(name, pair.v1, color, latest, 1)]
    })
  }
})
// Clicking anywhere in either panel picks that index for the trend above. It
// has to be onGridClick rather than onClick: these curves draw with
// showSymbol:false, so there is no series element to hit. The x-axis is a
// category axis of 0..359, so the converted value IS the index (setCoeffIndex
// rounds and clamps it).
useEchart(evolutionEl, evolutionOption, {
  onGridClick: x => setCoeffIndex(x)
})
</script>
