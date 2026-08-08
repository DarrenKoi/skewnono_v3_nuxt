<template>
  <div
    ref="rootEl"
    class="space-y-3"
  >
    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="dashboard-surface h-72 rounded-(--sk-r-card)"
      title="측정을 불러오는 중입니다."
    />

    <div
      v-else-if="analysis.focusError.value"
      class="dashboard-surface flex h-72 flex-col items-center justify-center gap-2 rounded-(--sk-r-card) text-center sk-body"
    >
      <span>측정을 불러오지 못했습니다.</span>
      <UButton
        color="primary"
        variant="soft"
        size="sm"
        icon="i-lucide-rotate-cw"
        label="다시 시도"
        @click="analysis.retryFocus()"
      />
    </div>

    <div
      v-else-if="!hasData"
      class="dashboard-surface flex h-72 items-center justify-center px-4 text-center sk-body"
    >
      “{{ analysis.activeParamLabel.value }}” 측정점이 없습니다. 다른 파라미터를 선택하세요.
    </div>

    <template v-else>
      <!-- View switch, in its own card rather than bare on the canvas. Two
           reasons it could not stay loose: --sk-chip-bg (L 0.95) and --sk-canvas
           (L 0.96) are one lightness step apart, so the segmented rail it used to
           wear was invisible exactly where it sat, and it was the only block on
           this view with no surface under it. The bar is H/W 관리's service-tab
           shape (HardwareView.vue) — dashboard-surface, tabs left — at the
           documented --sk-r-card radius rather than that call site's rounded-2xl,
           which DESIGN.md lists as drift.

           The pills take DESIGN.md's `sk-nav-pill` language (ink fill = NAVIGATE;
           the litmus test is "does pressing this change the view?" — it swaps the
           whole panel stack). The white-pill-on-tinted-rail skin they replace is
           the segmented control DESIGN.md files under Known Gaps.

           The <SkNavPill> COMPONENT is deliberately not used, only its visual
           language — it hardcodes `aria-pressed`, a toggle-button semantic that is
           invalid on `role="tab"`, and these are real tabs wired to a tabpanel
           below with roving-tabindex arrow keys. views/TimeSeries.vue made the
           same call for the same reason.

           Rejecting the component does NOT mean copying its look: these take the
           `sk-nav-pill` ROLE CLASSES from main.css, so a pill retone reaches them
           without anyone remembering they exist. (They restated the geometry in
           utilities until 2026-08-09 — the same drift TimeSeries had.) Sizing is
           the md tier, not that view's lg: the lens switch there picks the view,
           these pick a variant of the view you are already in. -->
      <section class="dashboard-surface flex flex-wrap items-center rounded-(--sk-r-card) px-3 py-2.5">
        <div
          role="tablist"
          aria-label="FDC 그래프 보기"
          class="inline-flex w-fit items-center gap-1.5"
          @keydown="onTabKeydown"
        >
          <button
            id="fdc-matrix-tab"
            type="button"
            role="tab"
            :tabindex="viewMode === 'matrix' ? 0 : -1"
            :aria-selected="viewMode === 'matrix'"
            aria-controls="fdc-matrix-panel"
            class="sk-nav-pill sk-nav-pill--md"
            :class="viewMode === 'matrix' ? 'sk-nav-pill--active' : 'sk-nav-pill--rest'"
            @click="selectView('matrix')"
          >
            <UIcon
              name="i-lucide-grid-3x3"
              class="size-3.5 shrink-0"
            />
            파라미터 매트릭스
          </button>
          <button
            id="fdc-individual-tab"
            type="button"
            role="tab"
            :tabindex="viewMode === 'individual' ? 0 : -1"
            :aria-selected="viewMode === 'individual'"
            aria-controls="fdc-individual-panel"
            class="sk-nav-pill sk-nav-pill--md"
            :class="viewMode === 'individual' ? 'sk-nav-pill--active' : 'sk-nav-pill--rest'"
            @click="selectView('individual')"
          >
            <UIcon
              name="i-lucide-activity"
              class="size-3.5 shrink-0"
            />
            개별 그래프
          </button>
        </div>
      </section>

      <div
        :id="activePanelId"
        role="tabpanel"
        :aria-labelledby="activeTabId"
        class="space-y-3"
      >
        <!-- Overview: every param at once, each in its own unit. The panes below
             stay the detailed reading; this is the scan layer. -->
        <EbeamSkewvoirPanelFrame
          v-if="viewMode === 'matrix'"
          title="파라미터 매트릭스"
          :meta="matrixMeta"
          icon="i-lucide-grid-3x3"
        >
          <template #actions>
            <USwitch
              v-model="hideUnavailable"
              size="xs"
              label="평가 불가 숨기기"
            />
          </template>
          <EbeamSkewvoirFdcParamMatrix
            :model="matrix"
            :colors="fdcColorByParam"
            @select="onSelect"
            @drill="drillTo"
          />
        </EbeamSkewvoirPanelFrame>

        <section
          v-if="viewMode === 'individual' && model.hasFdc"
          class="dashboard-surface rounded-(--sk-r-card) p-3"
          aria-labelledby="fdc-graph-selector-title"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2
              id="fdc-graph-selector-title"
              class="sk-title"
            >
              표시할 그래프
            </h2>
            <div class="flex items-center gap-1.5">
              <UButton
                size="xs"
                color="neutral"
                variant="soft"
                label="CD만 선택"
                @click="selectOnlyCd"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="soft"
                label="전체 선택"
                @click="selectAllGraphs"
              />
            </div>
          </div>
          <div
            class="mt-2 flex flex-wrap gap-1.5"
            role="group"
            aria-label="개별 그래프 선택"
          >
            <button
              type="button"
              :aria-pressed="selectedGraphSet.has(cdGraphId(analysis.activeParam.value))"
              class="rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-[11px] transition-colors"
              :class="selectedGraphSet.has(cdGraphId(analysis.activeParam.value))
                ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
                : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="onGraphToggle(cdGraphId(analysis.activeParam.value))"
            >
              CD · {{ analysis.activeParamLabel.value }}
            </button>
            <button
              v-for="series in model.fdc"
              :key="series.param"
              type="button"
              :aria-pressed="selectedGraphSet.has(fdcGraphId(series.param))"
              class="rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-[11px] transition-colors"
              :class="selectedGraphSet.has(fdcGraphId(series.param))
                ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
                : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="onGraphToggle(fdcGraphId(series.param))"
            >
              {{ series.param }}
            </button>
          </div>
        </section>

        <!-- Event lane — failure / image / alignment along the measurement order,
             sharing the panes' cursor. -->
        <EbeamSkewvoirPanelFrame
          title="측정 순서 (Sequence)"
          :meta="sequenceMeta"
          icon="i-lucide-git-commit-horizontal"
        >
          <template #actions>
            <div class="flex items-center gap-2">
              <span
                v-if="!model.integrity.matched && model.integrity.fdc > 0"
                class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)"
                :title="`측정 row ${model.integrity.rows}개 · dynamic FDC ${model.integrity.fdc}개 — 측정마다 FDC 1건이 있어야 합니다.`"
              >
                데이터 불일치 · row {{ model.integrity.rows }} / FDC {{ model.integrity.fdc }}
              </span>
              <USelect
                v-model="axisMode"
                size="xs"
                :items="axisItems"
                class="min-w-[8.5rem]"
              />
              <span class="sk-meta tabular-nums">
                cursor: {{ analysis.focusedSequence.value ?? '—' }}
              </span>
            </div>
          </template>
          <EbeamSkewvoirFdcSequenceEventLane
            :sequences="model.sequences"
            :events="model.events"
            :focused="analysis.focusedSequence.value"
            @select="onSelect"
          />
        </EbeamSkewvoirPanelFrame>

        <!-- CD pane — selected in the individual view. Different units stay in SEPARATE panes. -->
        <EbeamSkewvoirPanelFrame
          v-if="viewMode === 'individual' && showCdGraph"
          :title="`CD · ${analysis.activeParamLabel.value}`"
          :meta="cdMeta"
          icon="i-lucide-activity"
        >
          <EbeamSkewvoirFdcSequenceTrend
            :points="model.cd.points"
            :sequences="model.sequences"
            :name="analysis.activeParam.value"
            :unit="model.unit"
            :focused="analysis.focusedSequence.value"
            :color="cdColor"
            @select="onSelect"
          />
        </EbeamSkewvoirPanelFrame>

        <!-- Dynamic-FDC panes — one per param, each its own Y unit. -->
        <template v-if="viewMode === 'individual' && model.hasFdc">
          <EbeamSkewvoirPanelFrame
            v-for="series in selectedFdc"
            :key="series.param"
            :data-fdc-param="series.param"
            tabindex="-1"
            :title="`Dynamic FDC · ${series.param}`"
            :meta="fdcMeta(series)"
            icon="i-lucide-waves"
          >
            <EbeamSkewvoirFdcSequenceTrend
              :points="series.points"
              :sequences="model.sequences"
              :name="series.param"
              :unit="series.unit"
              :nominal="series.nominal"
              :focused="analysis.focusedSequence.value"
              :color="fdcColorByParam[series.param] ?? cdColor"
              @select="onSelect"
            />
          </EbeamSkewvoirPanelFrame>
        </template>

        <div
          v-if="viewMode === 'individual' && noGraphsSelected"
          class="dashboard-surface flex flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 py-6 text-center"
        >
          <p class="sk-title">
            선택된 그래프가 없습니다
          </p>
          <p class="sk-body">
            위 버튼에서 확인할 CD 또는 FDC 그래프를 선택하세요.
          </p>
        </div>

        <!-- No dynamic FDC — CD pane only, with the reason. -->
        <div
          v-if="!model.hasFdc"
          class="dashboard-surface flex flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 py-6 text-center"
        >
          <p class="sk-title">
            FDC 없음
          </p>
          <p class="sk-body">
            {{ model.fdcReason }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'
import { analyzeSequence, type FdcSeqSeries, type SequenceAxisMode, type SequenceSource } from '~/utils/skewvoirAnalysis/sequence'
import { buildParamMatrix } from '~/utils/skewvoirAnalysis/paramMatrix'
import {
  addGraphSelection,
  cdGraphId,
  fdcGraphId,
  graphSelectionIds,
  reconcileGraphSelection,
  selectCdOnly,
  toggleGraphSelection,
  type GraphSelectionId
} from '~/utils/skewvoirAnalysis/graphSelection'
import { assignCompareColors } from '~/utils/hardwareCompare'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

type FdcViewMode = 'matrix' | 'individual'

const viewMode = ref<FdcViewMode>('matrix')
const selectedGraphs = ref<GraphSelectionId[]>([])
const previousAvailableGraphs = ref<GraphSelectionId[]>([])

const hasData = computed(() =>
  props.analysis.siteRows.value.some(
    r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r)
  )
)

// One source feeds both the panes and the matrix, so "the overview and the
// detail cannot disagree about what was measured" is true by construction
// rather than by two call sites spelling the same fallbacks identically.
const source = computed<SequenceSource>(() => ({
  rows: props.analysis.siteRows.value,
  dynamic_fdc: props.analysis.focusFile.value?.dynamic_fdc ?? {},
  fdc_params: props.analysis.focusFile.value?.fdc_params ?? []
}))

// The shared-cursor sequence model for the FOCUS file + active parameter, on the
// axis the URL asks for.
const model = computed(() =>
  analyzeSequence(
    source.value,
    props.analysis.activeParam.value,
    props.analysis.activeUnit.value,
    props.analysis.fdcAxis.value
  )
)

const availableGraphIds = computed(() =>
  graphSelectionIds(
    props.analysis.activeParam.value,
    model.value.fdc.map(series => series.param)
  )
)

const graphResetKey = computed(() =>
  `${props.analysis.focusMsr.value ?? ''}\u0000${props.analysis.activeParam.value}`
)

watch(graphResetKey, () => {
  const next = availableGraphIds.value
  selectedGraphs.value = [...next]
  previousAvailableGraphs.value = [...next]
}, { immediate: true })

watch(availableGraphIds, (next) => {
  selectedGraphs.value = reconcileGraphSelection(
    selectedGraphs.value,
    previousAvailableGraphs.value,
    next
  )
  previousAvailableGraphs.value = [...next]
})

const selectedGraphSet = computed(() => new Set(selectedGraphs.value))
const showCdGraph = computed(() =>
  !model.value.hasFdc
  || selectedGraphSet.value.has(cdGraphId(props.analysis.activeParam.value))
)
const selectedFdc = computed(() =>
  model.value.fdc.filter(series =>
    selectedGraphSet.value.has(fdcGraphId(series.param))
  )
)
const noGraphsSelected = computed(() =>
  model.value.hasFdc
  && !showCdGraph.value
  && selectedFdc.value.length === 0
)

const selectAllGraphs = (): void => {
  selectedGraphs.value = [...availableGraphIds.value]
}

const selectOnlyCd = (): void => {
  selectedGraphs.value = selectCdOnly(props.analysis.activeParam.value)
}

const onGraphToggle = (id: GraphSelectionId): void => {
  selectedGraphs.value = toggleGraphSelection(selectedGraphs.value, id)
}

const tabOrder: FdcViewMode[] = ['matrix', 'individual']
const activeTabId = computed(() => `fdc-${viewMode.value}-tab`)
const activePanelId = computed(() => `fdc-${viewMode.value}-panel`)

const selectView = (mode: FdcViewMode): void => {
  viewMode.value = mode
}

const onTabKeydown = (event: KeyboardEvent): void => {
  const current = tabOrder.indexOf(viewMode.value)
  let next = current

  if (event.key === 'ArrowLeft') next = (current - 1 + tabOrder.length) % tabOrder.length
  else if (event.key === 'ArrowRight') next = (current + 1) % tabOrder.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = tabOrder.length - 1
  else return

  event.preventDefault()
  viewMode.value = tabOrder[next] ?? 'matrix'
  nextTick(() => {
    rootEl.value
      ?.querySelector<HTMLButtonElement>(`#fdc-${viewMode.value}-tab`)
      ?.focus()
  })
}

const axisItems = [
  { label: '파라미터 정렬', value: 'param' },
  { label: '전체 sequence', value: 'all' }
]

// v-model on a computed with an explicit setter, so the URL stays the single
// source of truth rather than a local ref shadowing it.
const axisMode = computed({
  get: () => props.analysis.fdcAxis.value,
  set: (v: SequenceAxisMode) => props.analysis.setFdcAxis(v)
})

// 평가 불가 파라미터를 매트릭스(와 그 tooltip)에서 숨기는 사용자 선택 —
// persisted, so the preference survives view swaps and reloads.
const hideUnavailable = useSkewvoirFdcHideUnavailable()

const matrix = computed(() =>
  buildParamMatrix(model.value, source.value, { hideUnavailable: hideUnavailable.value })
)

const matrixMeta = computed(() => {
  const base = `${matrix.value.rows.length} rows · ${matrix.value.columns} cols · CD 대비 상관`
  // Say what the toggle hid — a silently thinner matrix reads as "not measured".
  return matrix.value.hiddenUnavailable > 0
    ? `${base} · 평가 불가 ${matrix.value.hiddenUnavailable}개 숨김`
    : base
})

// Drill-down: bring the clicked param's full-size pane into view. `nearest` is
// deliberate — it is a no-op when the pane is already on screen, so a click
// meant only to move the cursor does not yank the page around. The nextTick
// wrapper follows MeasurementPoints.vue: the same click also moves the cursor,
// so let the resulting DOM settle before measuring scroll position.
//
// Scoped to this workbench's own root rather than a document-wide id: FDC param
// names come from an open office catalog and may contain spaces, and two
// workbenches on one page would otherwise fight over the same ids.
const rootEl = ref<HTMLElement | null>(null)

const drillTo = (param: string): void => {
  selectedGraphs.value = addGraphSelection(
    selectedGraphs.value,
    fdcGraphId(param)
  )
  viewMode.value = 'individual'

  nextTick(() => {
    requestAnimationFrame(() => {
      const target = rootEl.value
        ?.querySelector<HTMLElement>(`[data-fdc-param="${CSS.escape(param)}"]`)
      target?.focus({ preventScroll: true })
      target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  })
}

const fmt = (v: number): string => (Number.isFinite(v) ? v.toFixed(2) : '—')
const signed = (v: number): string => (Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(3)}` : '—')

// A scoped axis is a SUBSET of the MSR, so it says so — otherwise a subset
// reads as the whole run.
const sequenceMeta = computed(() => {
  const base = `${model.value.sequences.length} points · ${props.analysis.activeParamLabel.value}`
  return model.value.excludedFdc > 0
    ? `${base} · 타 parameter ${model.value.excludedFdc} 제외`
    : base
})

// Per-sequence stat meta — slope labelled "per sequence", never per second.
const cdMeta = computed(() => {
  const s = model.value.cd.stats
  return `start ${fmt(s.start)} · end ${fmt(s.end)} · range ${fmt(s.range)} ${s.unit} · slope ${signed(s.slope)} ${s.slopeUnit} · 결측 ${s.missing}`
})

const fdcMeta = (series: FdcSeqSeries): string => {
  const s = series.stats
  return `start ${fmt(s.start)} · end ${fmt(s.end)} · range ${fmt(s.range)} ${s.unit} · slope ${signed(s.slope)} ${s.slopeUnit}`
}

// Distinct accents per pane. Each pane is a SEPARATE chart instance, so ECharts
// would hand every one of them palette[0] — the colors have to be assigned here
// or the panes become indistinguishable.
//
// Keyed by PARAM NAME, not pane position, and by the same helper the matrix
// above uses: a param must be one colour in both, or clicking a cell would drop
// you on a differently-coloured pane. assignCompareColors reserves palette[0],
// which stays with the CD pane.
const sk = useChartPalette()
const { palette } = useEchartsTheme()
const cdColor = computed(() => sk.value.series)
const fdcColorByParam = computed(() =>
  assignCompareColors(model.value.fdc.map(s => s.param), palette.value)
)

// SHARED CURSOR: one move sets the focused sequence AND the focused site (chip)
// for that sequence — so CD, every FDC pane, the wafer scan-path (focusedSite)
// and any SEM image all point at the same sequence.
const onSelect = (sequence: number) => {
  props.analysis.setFocusedSequence(sequence)
  const chip = model.value.siteBySequence[sequence]
  if (chip) props.analysis.setFocusedSite(chip)
}
</script>
