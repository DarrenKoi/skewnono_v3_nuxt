<template>
  <!-- Multi-measurement comparison only. The single-MSR sequence workbench moved
       to the FDC 분석 view: it plots measurement ORDER, which is a different
       axis from this view's across-measurement trend, not a narrower one.

       Reading order: 무결성 → 파라미터 → 렌즈 → 활성 차트 → Sequence Trend. -->
  <div
    v-if="analysis.scope.value === 'set'"
    class="space-y-3"
  >
    <!-- Integrity. Cross-family picks now resolve like any other (the analysis
         reads BOTH families' histories), so the only failure left to report is
         a resolved measurement whose file the batch endpoint skipped: POST
         /api/msr-files silently skips MSRs it cannot find, so without this the
         miss would masquerade as “이 파라미터가 없다” and quietly shrink every
         denominator on the page.

         Gated on `setPending` — this compares against the batch's result.
         While the batch is in flight `loaded` is 0, so an ungated alert
         accuses the request of failing every single time, for as long as it
         takes. -->
    <UAlert
      v-if="!analysis.setPending.value && integrity.resolved > integrity.loaded"
      color="warning"
      variant="soft"
      icon="i-lucide-file-x"
      :title="`${integrity.resolved - integrity.loaded}개 측정의 파일을 불러오지 못했습니다.`"
      description="아래 집계의 분모에서 빠져 있습니다."
    />

    <EbeamSkewvoirTimeseriesParamCoverageList
      :options="analysis.paramOptions.value"
      :model-value="analysis.activeParam.value"
      @update:model-value="ws.setParam($event)"
    />

    <!-- Recipe mixing confounds the skew lens: an offset between two tools that
         ran different recipes is not attributable to the tools.

         On its own line rather than trailing the parameter chips: a warning
         wrapped into the middle of a chip flow reads as one more parameter, and
         it moves every time the list rewraps. -->
    <p
      v-if="integrity.recipeCount > 1"
      class="flex w-fit items-center gap-1.5 rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-1 text-[11px] text-(--sk-warn)"
    >
      <UIcon
        name="i-lucide-triangle-alert"
        class="size-3.5 shrink-0"
      />
      recipe {{ integrity.recipeCount }}종 혼재 · 장비 차이로 해석하기 어렵습니다.
    </p>

    <!-- Lens switch — the primary control on this page: it decides which of the
         three questions (추이 / 분포 / 장비 skew) the whole panel below answers.
         It was sized like an incidental filter (text-xs on a hairline track),
         so it read as decoration and users missed that the other two lenses
         existed. It now wears the app's standard segmented-track skin — h-9,
         text-sm, icon + label, active pill lifted on a white surface — the same
         one EquipmentStatusSubTabs and the Recipe TAT 전체 요약/디바이스별 toggle
         use, so it reads as a view switch on sight.

         There is no `UButtonGroup` in NuxtUI 4.10 (the registry has UFieldGroup
         and UTabs); this repo's precedent for exactly this control is a
         hand-rolled tablist with native buttons and a roving tabindex — see
         fdc/SequenceWorkbench.vue, whose keydown handling this mirrors.

         Hidden while loading and while there is nothing to show: an empty tab
         strip over a spinner offers a choice that does nothing. -->
    <div
      v-if="lensTabsVisible"
      ref="lensTabsEl"
      role="tablist"
      aria-label="Time-Series 보기"
      class="inline-flex w-fit items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
      @keydown="onLensKeydown"
    >
      <button
        v-for="lens in LENSES"
        :id="tabId(lens.value)"
        :key="lens.value"
        type="button"
        role="tab"
        :tabindex="ws.tsView.value === lens.value ? 0 : -1"
        :aria-selected="ws.tsView.value === lens.value"
        :aria-controls="panelId(lens.value)"
        class="inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors"
        :class="ws.tsView.value === lens.value
          ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="ws.setTsView(lens.value)"
      >
        <UIcon
          :name="lens.icon"
          class="size-4 shrink-0"
        />
        {{ lens.label }}
      </button>
    </div>

    <!-- The tab strip is conditional, so the panel only claims to be its tabpanel
         while that tab actually exists — a dangling aria-labelledby is worse than
         no relationship at all. -->
    <div
      :id="lensTabsVisible ? panelId(ws.tsView.value) : undefined"
      :role="lensTabsVisible ? 'tabpanel' : undefined"
      :aria-labelledby="lensTabsVisible ? tabId(ws.tsView.value) : undefined"
    >
      <EbeamSkewvoirPanelFrame
        :title="activeTitle"
        :meta="activeMeta"
        :icon="activeIcon"
      >
        <!-- Axis mode and baseline are per-lens view state carried in the URL, so
             they ride the trend panel's header the way FDC 분석 carries its axis
             select. The anomaly method + thresholds stay in the body row below:
             the header slot is `shrink-0`, so parking six controls in it would
             widen the panel past its container instead of wrapping. -->
        <template
          v-if="ws.tsView.value === 'trend'"
          #actions
        >
          <div class="flex items-center gap-2">
            <div class="flex items-center gap-0.5">
              <UButton
                v-for="opt in AXIS_OPTIONS"
                :key="opt.value"
                size="xs"
                color="neutral"
                :variant="ws.tsAxis.value === opt.value ? 'soft' : 'ghost'"
                :aria-pressed="ws.tsAxis.value === opt.value"
                :label="opt.label"
                :title="opt.hint"
                @click="ws.setTsAxis(opt.value)"
              />
            </div>
            <div class="flex items-center gap-0.5">
              <UButton
                v-for="opt in BASELINE_OPTIONS"
                :key="opt.value"
                size="xs"
                color="neutral"
                :variant="ws.tsBaseline.value === opt.value ? 'soft' : 'ghost'"
                :aria-pressed="ws.tsBaseline.value === opt.value"
                :label="opt.label"
                :title="opt.hint"
                @click="ws.setTsBaseline(opt.value)"
              />
            </div>
          </div>
        </template>

        <AppLoadingState
          v-if="analysis.setPending.value"
          variant="inline"
          class="h-72"
          title="추이 데이터를 불러오는 중입니다."
        />

        <!-- Fewer than two measurements: the empty state, NOT a lens. Placed
             ahead of the three lens branches so none of them can render a
             degenerate one-measurement view. It sits in the panel body rather
             than replacing the whole screen so the integrity alerts above —
             which are often the reason only one measurement survived — stay
             on screen. -->
        <div
          v-else-if="!hasComparableSetData"
          class="flex h-72 items-center justify-center sk-body"
        >
          {{ comparableCount === 1
            ? '측정 1개로는 비교할 수 없습니다 · 측정을 더 추가하세요.'
            : '비교할 측정을 추가하세요.' }}
        </div>

        <template v-else-if="ws.tsView.value === 'trend' && analysis.trendPoints.value.length">
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <USelect
              v-model="anomalyCfg.method"
              size="xs"
              :items="methodItems"
              class="min-w-[11rem]"
            />
            <template v-if="anomalyCfg.method === 'range'">
              <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
                주의 ±<UInput
                  v-model.number="anomalyCfg.range.watchPct"
                  type="number"
                  min="0"
                  size="xs"
                  class="w-14"
                />%
              </label>
              <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
                이상 ±<UInput
                  v-model.number="anomalyCfg.range.abnormalPct"
                  type="number"
                  min="0"
                  size="xs"
                  class="w-14"
                />%
              </label>
            </template>
            <template v-else>
              <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
                주의 ±<UInput
                  v-model.number="anomalyCfg.stddev.watchK"
                  type="number"
                  min="0"
                  size="xs"
                  class="w-14"
                />σ
              </label>
              <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
                이상 ±<UInput
                  v-model.number="anomalyCfg.stddev.abnormalK"
                  type="number"
                  min="0"
                  size="xs"
                  class="w-14"
                />σ
              </label>
            </template>
            <span class="sk-meta tabular-nums">
              주의 {{ analysis.trendSummary.value.watch }} · 이상 {{ analysis.trendSummary.value.abnormal }} / {{ analysis.trendPoints.value.length }} MSR
            </span>
            <SkAnomalyLegend
              class="ml-auto"
              :method="anomalyCfg.method"
              :range="anomalyCfg.range"
              :stddev="anomalyCfg.stddev"
            />
          </div>
          <EbeamSkewvoirTimeSeriesChart
            :points="analysis.trendPoints.value"
            :parameter="analysis.activeParam.value"
            :unit="analysis.activeUnit.value"
            :axis-mode="ws.tsAxis.value"
            :baseline="ws.tsBaseline.value"
            @select="analysis.setFocusedMsr($event)"
          />
        </template>

        <!-- One box per measurement. Rotated labels + zoom because a curated set
             runs to 30 groups, which the default flat labels cannot carry. -->
        <EbeamSkewvoirDistributionChart
          v-else-if="ws.tsView.value === 'dist' && analysis.distributionGroups.value.length"
          :groups="analysis.distributionGroups.value"
          :unit="analysis.activeUnit.value"
          mode="Box"
          rotate-labels
          zoomable
        />

        <!-- No `.length` guard: buildToolSkew returns [] for BOTH “one tool” and
             “no data”, and only the panel (which also gets toolCount) can tell
             those apart. -->
        <EbeamSkewvoirTimeseriesToolSkewPanel
          v-else-if="ws.tsView.value === 'skew'"
          :rows="analysis.toolSkewRows.value"
          :tool-count="analysis.toolCount.value"
          :unit="analysis.activeUnit.value"
        />

        <div
          v-else
          class="flex h-72 items-center justify-center sk-body"
        >
          비교할 측정을 추가하세요.
        </div>
      </EbeamSkewvoirPanelFrame>
    </div>

    <!-- Sequence Trend plots each measurement's INTERNAL order — a different
         axis from the three lenses above, not a fourth one of them, so it stays
         put rather than joining the switch. The whole set is overlaid, one line
         per measurement colored by tool, with the focus line emphasized.

         The meta names chip (x, y) because the sequence is a die-to-die route,
         not a clock: without that, a rise along the axis is read as drift over
         time when it may be an ordinary across-wafer signature. The per-point
         die is in the chart's tooltip. -->
    <EbeamSkewvoirPanelFrame
      title="Sequence Trend"
      :meta="`${analysis.sequenceGroups.value.length}개 측정 · chip (x, y) 이동 순서 · focus ${analysis.focusRow.value?.lot_id ?? '—'}`"
      icon="i-lucide-activity"
    >
      <template #actions>
        <SkAnomalyBadge :verdict="analysis.focusVerdict.value" />
      </template>
      <EbeamSkewvoirSequenceTrend
        v-if="analysis.sequenceGroups.value.length"
        :groups="analysis.sequenceGroups.value"
        :focus-msr="analysis.focusMsr.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
      />
      <div
        v-else
        class="flex h-56 items-center justify-center sk-body"
      >
        이 파라미터의 sequence 데이터가 없습니다.
      </div>
    </EbeamSkewvoirPanelFrame>
  </div>

  <div
    v-else
    class="dashboard-surface flex h-72 flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 text-center"
  >
    <p class="sk-title">
      Time-Series
    </p>
    <p class="sk-body">
      MSR을 2개 이상 선택하면 측정 간 추이를 비교합니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { TsAxisMode, TsBaseline, TsView } from '~/utils/skewvoirAnalysis/types'
import { placeTrendPoints } from '~/utils/skewvoirAnalysis/timeSeries'

// `ws` carries the URL-pinned lens, axis mode and baseline; `analysis` carries
// everything derived from the loaded set.
const props = defineProps<{
  analysis: SkewvoirAnalysis
  ws: SkewvoirWorkspace
}>()

// Destructure the mutable shared state ref into a local so v-model bindings do
// not trigger vue/no-mutating-props (anomalyCfg is useState-backed reactive state,
// not a plain prop value — accessing it through a local ref is safe).
const anomalyCfg = props.analysis.anomalyCfg

const methodItems = [
  { label: '범위(%)', value: 'range' },
  { label: '표준편차(σ) · 진단', value: 'stddev' }
]

// The icon is part of the lens definition, not a separate lookup — the tab strip
// and the active panel header both read it here, so they cannot disagree.
const LENSES: readonly { value: TsView, label: string, icon: string }[] = [
  { value: 'trend', label: '추이', icon: 'i-lucide-trending-up' },
  { value: 'dist', label: '분포', icon: 'i-lucide-chart-candlestick' },
  { value: 'skew', label: '장비 skew', icon: 'i-lucide-scale' }
]
const LENS_ORDER: readonly TsView[] = LENSES.map(l => l.value)

const AXIS_OPTIONS: readonly { value: TsAxisMode, label: string, hint: string }[] = [
  { value: 'time', label: '시간', hint: '측정 시각 기준으로 배치합니다.' },
  { value: 'order', label: '순서', hint: '측정 순서대로 균등 간격으로 배치합니다.' },
  { value: 'eqp', label: '장비', hint: '장비별 열로 모아 배치합니다.' }
]

// `원시값` read as jargon for "the number before we did something to it", which
// is not what this toggle offers: the choice is between the measured value and
// its distance from the set's median. `측정값` names the thing itself and pairs
// cleanly with `잔차` — 측정값을 볼 것인가, 세트 기준과의 잔차를 볼 것인가.
const BASELINE_OPTIONS: readonly { value: TsBaseline, label: string, hint: string }[] = [
  { value: 'raw', label: '측정값', hint: '측정된 값을 그대로 표시합니다.' },
  { value: 'resid', label: '잔차', hint: '세트 기준(측정 평균들의 중앙값) 대비 차이를 표시합니다.' }
]

const tabId = (lens: TsView): string => `ts-lens-${lens}-tab`
const panelId = (lens: TsView): string => `ts-lens-${lens}-panel`

const integrity = computed(() => props.analysis.integrity.value)

// How many measurements the lenses actually have to work with — the wider of
// the two derivations, mirroring what each lens draws from.
const comparableCount = computed(() => Math.max(
  props.analysis.trendPoints.value.length,
  props.analysis.distributionGroups.value.length
))

// TWO measurements is the floor for every lens, not one. At n=1 the trend is a
// single dot whose 세트 기준 is its own mean, the distribution is one box with
// nothing beside it, and the skew lens reads 단일 장비 — three degenerate views
// of a comparison that has no second term. The spec puts that case in the empty
// state, and it is one click away (the analyze button only requires a non-empty
// selection, and openAnalysisSet always writes scope=set).
const hasComparableSetData = computed(() => comparableCount.value >= 2)

const lensTabsVisible = computed(() =>
  !props.analysis.setPending.value && hasComparableSetData.value
)

const lensTabsEl = ref<HTMLElement | null>(null)

// Roving focus across the tab strip, mirroring fdc/SequenceWorkbench.vue.
// `.focus()` works on a tabindex="-1" button, so the move does not have to wait
// for the URL round-trip to flip which tab carries tabindex 0.
const onLensKeydown = (event: KeyboardEvent): void => {
  const current = LENS_ORDER.indexOf(props.ws.tsView.value)
  let next = current

  if (event.key === 'ArrowLeft') next = (current - 1 + LENS_ORDER.length) % LENS_ORDER.length
  else if (event.key === 'ArrowRight') next = (current + 1) % LENS_ORDER.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = LENS_ORDER.length - 1
  else return

  event.preventDefault()
  const target = LENS_ORDER[next] ?? 'trend'
  props.ws.setTsView(target)
  nextTick(() => {
    lensTabsEl.value?.querySelector<HTMLButtonElement>(`#${tabId(target)}`)?.focus()
  })
}

// --- Panel meta: report what silently fell out, never just what is drawn ---

const loadedCount = computed(() => integrity.value.loaded)
const trendCount = computed(() => props.analysis.trendPoints.value.length)

// Measurements whose file loaded but does not carry the active parameter. This
// is the denominator behind every number on the page, so it is stated rather
// than left for the reader to infer from a shorter-than-expected chart.
const missingParam = computed(() => Math.max(0, loadedCount.value - trendCount.value))
const missingParamMeta = computed(() =>
  missingParam.value ? ` · 파라미터 없음 ${missingParam.value}/${loadedCount.value}` : ''
)

// A measurement whose timestamp will not parse has no position on a time axis,
// so the chart drops it — invisibly, unless it is counted here. Counted with
// placeTrendPoints, the SAME function the chart draws with, so this figure can
// never disagree with what is on screen.
const unplaceable = computed(() =>
  props.ws.tsAxis.value === 'time'
    ? trendCount.value - placeTrendPoints(props.analysis.trendPoints.value, 'time').length
    : 0
)

// A box built from fewer than 4 sites is a shape nobody can read. Counted over
// the measurements that DO carry the parameter, so one dropped for having no
// measured site at all is reported here rather than vanishing between the two
// numbers.
const thinGroups = computed(() => {
  const groups = props.analysis.distributionGroups.value
  const dropped = Math.max(0, trendCount.value - groups.length)
  return dropped + groups.filter(g => g.values.length < 4).length
})

const activeTitle = computed(() => ({
  trend: 'Multi-Measurement Trend',
  dist: '측정별 분포',
  skew: '장비 skew'
}[props.ws.tsView.value]))

// Read off LENSES so the panel header and the tab it belongs to always show the
// same icon.
const activeIcon = computed(() =>
  LENSES.find(l => l.value === props.ws.tsView.value)?.icon ?? 'i-lucide-trending-up'
)

const activeMeta = computed(() => {
  const param = props.analysis.activeParamLabel.value
  if (props.ws.tsView.value === 'dist') {
    const thin = thinGroups.value ? ` · 측정점 4개 미만 ${thinGroups.value}개` : ''
    return `${props.analysis.distributionGroups.value.length}개 측정 · ${param}${missingParamMeta.value}${thin}`
  }
  if (props.ws.tsView.value === 'skew') {
    return `${props.analysis.toolCount.value}개 장비 · 세트 기준 대비${missingParamMeta.value}`
  }
  // The min/max band is not drawn under the eqp axis, so the meta must not
  // claim it is.
  if (props.ws.tsAxis.value === 'eqp') {
    return `mean per 측정 · 장비별 · ${param}${missingParamMeta.value}`
  }
  const hidden = unplaceable.value ? ` · 시간축 배치 불가 ${unplaceable.value}개` : ''
  return `mean ± min/max · ${param}${missingParamMeta.value}${hidden}`
})
</script>
