<template>
  <!-- Multi-measurement comparison only. The single-MSR sequence workbench moved
       to the FDC 분석 view: it plots measurement ORDER, which is a different
       axis from this view's across-measurement trend, not a narrower one.

       Reading order: 무결성 → 파라미터 → 렌즈 → 조건 경고 → 활성 차트 →
       Sequence Trend. -->
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

    <!-- Lens switch — the primary control on this page: it decides which of the
         three questions (추이 / 분포 / 장비 skew) the whole panel below answers.

         It has now been resized twice. It started as an incidental filter
         (text-xs on a hairline track), which read as decoration and hid that the
         other two lenses existed; the fix was the app's standard segmented-track
         skin — h-9 / text-sm / white pill on a zinc rail — shared with
         EquipmentStatusSubTabs and the Recipe TAT 전체 요약/디바이스별 toggle.
         That was still too quiet, because the shared skin is built for SUB-tabs:
         controls that pick a variant of the view you are already in. This one
         picks the view.

         So it deliberately leaves that skin and takes DESIGN.md's `sk-nav-pill`
         language instead — ink fill, --sk-r-nav radius, 15px — which the
         selection-primitive decision flow assigns to exactly this job
         ("changes route/view → sk-nav-pill", and it lists section toggles like
         BSM/FDC/BM·PM as the precedent). Do not "restore consistency" with
         EquipmentStatusSubTabs here: outranking a sub-tab strip is the point.

         The <SkNavPill> COMPONENT is deliberately not used, only its visual
         language. The pill hardcodes `aria-pressed`, which is a toggle-button
         semantic and invalid on `role="tab"` — and these are real tabs, wired to
         a tabpanel below via aria-controls/aria-labelledby with roving-tabindex
         arrow keys (mirroring fdc/SequenceWorkbench.vue). Adopting the component
         would trade working keyboard navigation for markup tidiness.

         It takes the pill's ROLE CLASSES (`sk-nav-pill` + size + state, in
         main.css) rather than restating its geometry in utilities. Rejecting
         the component was sound; copying its `h-11 px-5 text-[15px]` was how
         that sound decision quietly recreated the dependency, so a pill retone
         would move SkNavPill and leave these tabs behind. Same rule, different
         markup around it.

         Hidden while loading and while there is nothing to show: an empty tab
         strip over a spinner offers a choice that does nothing.

         It sits on its own `dashboard-surface` card, titled, exactly like the
         파라미터 control above it — and for the same reason that one grew a
         panel. A bare pill row on the page background read as loose furniture
         between two cards, so the page's TWO controls (which parameter,
         which question) were styled as if only one of them mattered. Matching
         the card makes them a pair; the pill vs. chip difference INSIDE the
         cards is then free to carry its real meaning (view change vs. data
         narrowing) instead of being confused with "one of these is a
         control and one isn't". -->
    <div
      v-if="lensTabsVisible"
      class="dashboard-surface flex flex-col gap-2 rounded-(--sk-r-card) px-3 py-2.5"
    >
      <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h3 class="sk-panel-title">
          보기
        </h3>
        <p class="sk-hint">
          아래 패널이 답할 질문을 고릅니다.
        </p>
      </div>
      <div
        ref="lensTabsEl"
        role="tablist"
        aria-label="Time-Series 보기"
        class="inline-flex w-fit items-center gap-1.5"
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
          class="sk-nav-pill sk-nav-pill--lg"
          :class="ws.tsView.value === lens.value ? 'sk-nav-pill--active' : 'sk-nav-pill--rest'"
          @click="ws.setTsView(lens.value)"
        >
          <UIcon
            :name="lens.icon"
            class="size-[18px] shrink-0"
          />
          {{ lens.label }}
        </button>
      </div>
    </div>

    <!-- Recipe mixing qualifies a NUMBER, not the page, so it is stated next to
         the number: between the lens switch and the panel it applies to, rather
         than above the switch where it read as a property of the whole set.

         A tool's measured response is a response to a measurement CONDITION —
         recipe fixes mag, pixel, vac, method and site layout — so two tools that
         ran different recipes differ even when the tools are identical. That
         misattribution only happens in a view that invites a tool-to-tool
         reading: the skew lens, and the trend lens under the 장비 axis. Under
         추이/분포 the same mixing shows up as a level offset the reader can see
         in the chart, and claiming 장비 차이 there is simply false. -->
    <p
      v-if="recipeMixWarning"
      class="flex w-fit items-center gap-1.5 rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2.5 py-1.5 text-sm text-(--sk-warn)"
    >
      <UIcon
        name="i-lucide-triangle-alert"
        class="size-4 shrink-0"
      />
      recipe {{ integrity.recipeCount }}종 혼재 · 장비 간 차이에 recipe 차이가 섞여 있습니다.
    </p>

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
        title-size="md"
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
              size="sm"
              :items="methodItems"
              class="min-w-[12rem]"
            />
            <template v-if="anomalyCfg.method === 'range'">
              <label class="flex items-center gap-1.5 sk-field-label">
                주의 ±<UInput
                  v-model.number="anomalyCfg.range.watchPct"
                  type="number"
                  min="0"
                  size="sm"
                  class="w-16"
                />%
              </label>
              <label class="flex items-center gap-1.5 sk-field-label">
                이상 ±<UInput
                  v-model.number="anomalyCfg.range.abnormalPct"
                  type="number"
                  min="0"
                  size="sm"
                  class="w-16"
                />%
              </label>
            </template>
            <template v-else>
              <label class="flex items-center gap-1.5 sk-field-label">
                주의 ±<UInput
                  v-model.number="anomalyCfg.stddev.watchK"
                  type="number"
                  min="0"
                  size="sm"
                  class="w-16"
                />σ
              </label>
              <label class="flex items-center gap-1.5 sk-field-label">
                이상 ±<UInput
                  v-model.number="anomalyCfg.stddev.abnormalK"
                  type="number"
                  min="0"
                  size="sm"
                  class="w-16"
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

        <!-- No `.length` guard: buildToolSkew returns no rows for “one tool”,
             “no data” AND “recipe fully confounded with tool”, and only the
             panel (which also gets toolCount and the recipe counts) can tell
             those three apart. -->
        <EbeamSkewvoirTimeseriesToolSkewPanel
          v-else-if="ws.tsView.value === 'skew'"
          :skew="analysis.toolSkew.value"
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
      title-size="md"
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

const integrity = computed(() => props.analysis.integrity.value)

// What the residual is measured FROM. With one recipe in the set it is the
// set-wide median, as before; with more, each measurement is centered on its
// own recipe's median so a residual is a distance from measurements taken the
// same way rather than from a mixture of conditions.
const baselineLabel = computed(() => (integrity.value.recipeCount > 1 ? 'recipe별 기준' : '세트 기준'))

// `원시값` read as jargon for "the number before we did something to it", which
// is not what this toggle offers: the choice is between the measured value and
// its distance from the baseline. `측정값` names the thing itself and pairs
// cleanly with `잔차` — 측정값을 볼 것인가, 기준과의 잔차를 볼 것인가.
//
// The hint names which baseline, and so has to be computed: a static
// "세트 기준(측정 평균들의 중앙값)" would describe the wrong arithmetic for
// every mixed-recipe set.
const BASELINE_OPTIONS = computed<readonly { value: TsBaseline, label: string, hint: string }[]>(() => [
  { value: 'raw', label: '측정값', hint: '측정된 값을 그대로 표시합니다.' },
  {
    value: 'resid',
    label: '잔차',
    hint: integrity.value.recipeCount > 1
      ? 'recipe별 기준(같은 recipe 측정 평균들의 중앙값) 대비 차이를 표시합니다.'
      : '세트 기준(측정 평균들의 중앙값) 대비 차이를 표시합니다.'
  }
])

const tabId = (lens: TsView): string => `ts-lens-${lens}-tab`
const panelId = (lens: TsView): string => `ts-lens-${lens}-panel`

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

// Views whose numbers are attributed to a tool: the skew lens (every row is a
// per-tool offset from the set baseline) and the trend lens under the 장비 axis
// (measurements are collected into per-tool columns to be read against each
// other). These are the two places recipe mixing turns into a claim about
// hardware that the data does not support.
const toolAttributionView = computed(() =>
  props.ws.tsView.value === 'skew'
  || (props.ws.tsView.value === 'trend' && props.ws.tsAxis.value === 'eqp')
)

// Shares `lensTabsVisible`'s gate so the warning never qualifies a spinner or
// the empty state — there is no number on screen to be wrong yet.
const recipeMixWarning = computed(() =>
  lensTabsVisible.value && integrity.value.recipeCount > 1 && toolAttributionView.value
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
    return `${props.analysis.toolCount.value}개 장비 · ${baselineLabel.value} 대비${missingParamMeta.value}`
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
