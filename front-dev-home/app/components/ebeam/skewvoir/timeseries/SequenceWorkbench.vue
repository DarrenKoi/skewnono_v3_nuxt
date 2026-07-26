<template>
  <div
    ref="rootEl"
    class="space-y-3"
  >
    <div
      v-if="analysis.focusPending.value"
      class="dashboard-surface flex h-72 items-center justify-center gap-2 rounded-(--sk-r-card) sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      측정을 불러오는 중…
    </div>

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
      <!-- Event lane — failure / image / alignment along the measurement order,
           sharing the panes' cursor. -->
      <EbeamSkewvoirPanelFrame
        title="측정 순서 (Sequence)"
        :meta="`${model.sequences.length} points · ${analysis.activeParamLabel.value}`"
        icon="i-lucide-git-commit-horizontal"
      >
        <template #actions>
          <span class="sk-meta tabular-nums">
            cursor: {{ analysis.focusedSequence.value ?? '—' }}
          </span>
        </template>
        <EbeamSkewvoirTimeseriesSequenceEventLane
          :sequences="model.sequences"
          :events="model.events"
          :focused="analysis.focusedSequence.value"
          @select="onSelect"
        />
      </EbeamSkewvoirPanelFrame>

      <!-- Overview: every param at once, each in its own unit. The panes below
           stay the detailed reading; this is the scan layer. -->
      <EbeamSkewvoirPanelFrame
        title="파라미터 매트릭스"
        :meta="`${matrix.rows.length} rows · ${matrix.columns} cols · CD 대비 상관`"
        icon="i-lucide-grid-3x3"
      >
        <template #actions>
          <span
            v-if="matrix.demoCoupled"
            class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)"
          >
            데모 데이터 · 방법 검증 불가
          </span>
        </template>
        <EbeamSkewvoirTimeseriesParamMatrix
          :model="matrix"
          :colors="fdcColorByParam"
          @select="onSelect"
          @drill="drillTo"
        />
      </EbeamSkewvoirPanelFrame>

      <!-- CD pane — always present. Different units go in SEPARATE panes. -->
      <EbeamSkewvoirPanelFrame
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
      <template v-if="model.hasFdc">
        <!-- data-fdc-param is the matrix's drill-down scroll target. It falls
             through to PanelFrame's root <section>, so no wrapper is needed. -->
        <EbeamSkewvoirPanelFrame
          v-for="series in model.fdc"
          :key="series.param"
          :data-fdc-param="series.param"
          :title="`Dynamic FDC · ${series.param}`"
          :meta="fdcMeta(series)"
          icon="i-lucide-waves"
        >
          <template #actions>
            <span class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)">
              데모 데이터 · 방법 검증 불가
            </span>
          </template>
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

      <!-- No dynamic FDC — CD pane only, with the reason. -->
      <div
        v-else
        class="dashboard-surface flex flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 py-6 text-center"
      >
        <p class="sk-title">
          FDC 없음
        </p>
        <p class="sk-body">
          {{ model.fdcReason }}
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'
import { analyzeSequence, type FdcSeqSeries, type SequenceSource } from '~/utils/skewvoirAnalysis/sequence'
import { buildParamMatrix } from '~/utils/skewvoirAnalysis/paramMatrix'
import { assignCompareColors } from '~/utils/hardwareCompare'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

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

// The shared-cursor sequence model for the FOCUS file + active parameter.
const model = computed(() =>
  analyzeSequence(source.value, props.analysis.activeParam.value, props.analysis.activeUnit.value)
)

const matrix = computed(() => buildParamMatrix(model.value, source.value))

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
  nextTick(() => {
    rootEl.value
      ?.querySelector(`[data-fdc-param="${CSS.escape(param)}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

const fmt = (v: number): string => (Number.isFinite(v) ? v.toFixed(2) : '—')
const signed = (v: number): string => (Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(3)}` : '—')

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
