<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fab}`"
      :title="view.title"
      :subtitle="view.subtitle"
      :cadence="cadence"
      :as-of="asOf"
      :stats="metaStats"
    >
      <!-- Beside the title, in MetaBar's own toggle cell — the same place
           장비 상태 puts its 장비 리스트/스토리지 pair. -->
      <template #toggle>
        <EbeamLabSubTabs :slug="slug" />
      </template>
    </EbeamMetaBar>

    <!-- The scope bar renders WHATEVER the payload says, including `available:
         false`, and it renders while the payload is still in flight. It used to
         be a side rail sharing a `v-else` with the results, so an empty answer
         took the controls down with it — and the commonest cause of an empty
         answer is the scope itself (a recipe with no pair, a parameter nobody
         measured, a stored pick that no longer applies). The one control that
         could fix it was the one thing removed from the screen. Only the RESULTS
         collapse.

         수집 기간 is NOT in this bar: it sits beside the 데이터 요청 button
         below, because it is part of asking, not of naming what to look at. -->
    <EbeamScopeBar hint="고른 recipe 의 측정 데이터로 계산합니다. 이 설정은 이 브라우저에 저장되고, 두 화면이 함께 씁니다.">
      <template #recipe>
        <EbeamScopeRecipe
          :recipe-id="recipeId"
          :recipe-names="recipeNames"
          :recipes-pending="recipesPending"
          :recipes-without-a-pair="recipesWithoutAPair"
          @update:recipe-id="onRecipe"
        />
      </template>
    </EbeamScopeBar>

    <!-- 장비 모델 그룹 — 비교에 넣을 장비. roster 는 sem-list 에서 오므로 요청
         전에도 고를 수 있고, 여기서 고른 장비만 서버에 요청합니다(2026-08-28).
         결과는 2대 이상일 때만 계산됩니다. -->
    <EbeamToolGroupBar
      :tools="roster"
      :selected="pickedTools"
      :deviations="fleetDeviations"
      :answered="answeredTools"
      :pending="rosterPending"
      hint="비교에 넣을 장비를 모델 그룹별로 고릅니다 — 고른 장비의 데이터만 서버에서 모읍니다. 두 화면이 함께 씁니다."
      @update:selected="onSelectedTools"
    />

    <!-- 수집 기간 · 데이터 요청 — 조건이 다 정해진 뒤 한 번 묻습니다. 한 번의
         클릭이 두 화면의 데이터를 다 모으므로, 탭을 바꾸는 데에는 다시 묻지
         않습니다 — 그것이 두 페이지를 하나로 합친 이유입니다. -->
    <EbeamRequestBar
      :window-weeks="windowWeeks"
      :tool-count="pickedTools.length"
      :has-recipe="scopeReady"
      :pending="pending"
      :stale="stale"
      :fetched-at="payload?.fetched_at ?? null"
      @update:window-weeks="onWindow"
      @request="request"
    />

    <!-- 튜닝할 장비 — 이 화면의 주어이고 아래 결과가 전부 이 한 대를 기준으로
         계산되지만, 그 계산이 성립하려면 먼저 비교 대상(recipe)과 장비 모델
         그룹이 정해져 있어야 합니다 — 어느 집합 안에서 고르는지가 정해지지
         않은 상태의 선택은 무엇을 고르는 것인지 말할 수 없습니다.

         The pm roster is its own request and does not ride on the recipe, so
         this bar is never locked: it lists the whole fab roster whatever the
         group above selects, and picking a tool the 장비 모델 그룹 bar left out
         is a legitimate question — it is exactly the "would this one get in"
         case this view exists to answer, and `basis` below pins such a pick into
         the matrices for it. The 그룹 badge simply does not appear until there
         is a group to be in. -->
    <EbeamPmPlanningToolPicker
      v-if="has('pm')"
      :rows="pickerRows"
      :picked="picked"
      :pending="pmPending"
      :awaiting="!pmFleet"
      @update:picked="picked = $event"
    />

    <!-- 분석 조건 — 비교 대상이 정해진 뒤의 선택. parameter 목록은 그 recipe 의
         측정 데이터(payload)에서 오므로, recipe 전에는 고를 것이 없습니다.
         Always mounted, disabled until the results can be computed. -->
    <EbeamAnalysisBar :lock="lock">
      <template #parameter>
        <EbeamScopeParameter
          :parameters="parameters"
          :parameter-names="parameterNames"
          :lock="lock"
          @update:parameters="onParameters"
        />
      </template>

      <!-- Slotted, not passed down: the knob fires on every drag frame, and a
           prop through the bar would re-render the parameter menu with it.
           Drawn in BOTH views since the merge — the tolerance defines the group
           the PM targets are aimed at, so a PM 플래닝 that could not turn it was
           a page that had to caption "TTTM 페이지의 설정을 따릅니다" and then
           use the server default anyway. -->
      <template #panels>
        <EbeamLabPanelPicker
          :panels="panels"
          @update:panels="setPanels"
        />
      </template>

      <template #trailing="{ disabled }">
        <EbeamToleranceKnob
          v-if="payload"
          v-model="tolerance"
          :range="payload.tolerance_range"
          :tolerance-index="toleranceIndex"
          :disabled="disabled"
          @commit="onTolerance"
        />
      </template>
    </EbeamAnalysisBar>

    <!-- The gate is the RECIPE alone. The server does answer without one (it
         folds every measured recipe together), but that answer is a fleet-wide
         average nobody asked for, and it renders identically to a deliberately
         scoped one — so the page would be quoting a comparison the user never
         chose. Deliberately the same gate in both views: they describe one group
         from one scope, so a recipe that opens the results on one must open them
         on the other. The parameter stays optional: folding every measured
         feature is a legitimate answer, and its list only exists once this
         payload has landed. -->
    <AppEmptyState
      v-if="!scopeReady"
      title="비교 대상을 선택하세요."
      description="위 비교 대상에서 recipe 를 고르면 그 recipe 가 점유한 셀로 아래 켜 둔 분석을 계산합니다."
      hint="recipe 를 고르면 그 측정 데이터에서 parameter 를 고를 수 있습니다 — 비워 두면 측정 항목을 모두 합쳐 판정합니다."
      icon="i-lucide-mouse-pointer-click"
    />

    <!-- Gated on the CHECK half only: the map and the verdicts paint as soon as
         the matrices arrive, and the pm-fed cards degrade cleanly while their
         own request is still in flight. AND-ing both made the fast payload wait
         for the slow one. -->
    <AppLoadingState
      v-else-if="tttmPending"
      title="측정 데이터를 불러오는 중입니다."
    />

    <!-- Nothing asked yet. The old pages fetched on load; this one waits for
         the button, and says so where the results will appear. -->
    <AppEmptyState
      v-else-if="!payload"
      title="데이터를 요청하십시오."
      description="위 장비 모델 그룹과 수집 기간을 정한 뒤 데이터 요청을 누르면 고른 장비의 run 을 서버에서 모읍니다."
      icon="i-lucide-database"
    />

    <!-- The shared empty-state shell, not a hand-rolled card: an unavailable
         payload is a legitimate answer ("nothing to compare"), which is the same
         shape of event AppEmptyState already owns. -->
    <AppEmptyState
      v-else-if="!payload?.available"
      title="계산할 결과가 없습니다."
      :description="payload?.summary ?? '데이터를 불러오지 못했습니다.'"
      hint="위에서 recipe · parameter · 장비를 바꾸어 다시 계산하실 수 있습니다."
      icon="i-lucide-scale"
    />

    <!-- One tool is not a comparison. The tool bar lets the selection drop
         to one or none (that is what 해제 means), and this is where the page
         says so instead of drawing empty cards. -->
    <AppEmptyState
      v-else-if="basis.length < 2"
      title="비교할 장비를 2대 이상 고르세요."
      description="위 장비 모델 그룹에서 장비를 고르면 그 장비들로 N배화 그룹과 스큐를 계산합니다."
      icon="i-lucide-mouse-pointer-click"
    />

    <div
      v-else
      class="flex min-w-0 flex-col gap-3"
    >
      <!-- The payload lags the scope: the results below are still the LAST
           answer, and must not be read as the current question's. Drawn, not
           hidden — an old answer with a label beats a blank page while the
           reader decides whether to re-ask. -->
      <div
        v-if="stale"
        class="rounded-[var(--sk-r-card)] border border-(--sk-warn-border) bg-(--sk-warn-soft) px-4 py-2.5 sk-meta leading-relaxed"
      >
        <span class="sk-title">조건이 바뀌었습니다</span> — 아래 결과는 마지막 요청
        <span class="font-mono tabular-nums">{{ asOf }}</span> 기준입니다. 위 데이터 요청을 누르면 반영됩니다.
      </div>

      <!-- What the knob and the picks currently cost, in one line. The numbers
           all appear again below in their own cards; this is the roll-up that
           makes dragging the slider legible without hunting for what moved. -->
      <div class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5">
        <!-- `.sk-meta` for the sentence and `.sk-value-num` for each number, per
             DESIGN.md §Colors' litmus — "value → ink; label → ink-muted". -->
        <p
          v-if="has('verdict')"
          class="sk-meta leading-relaxed"
        >
          <span class="sk-title">이 설정에서</span> —
          <!-- "셀 합계" is load-bearing: the matrix card below reports the
               failing pairs of ONE cell, and the two numbers differ by design.
               Unlabelled they read as the same count disagreeing with itself. -->
          점유 셀 <span class="sk-value-num">{{ rankedCells.length }}</span>개 ·
          불합격 장비쌍 <span class="sk-value-num">{{ failingPairs }}</span>쌍 (셀 합계)
          <template v-if="worstCell?.worstPair">
            · 최악 <span class="sk-value-num">{{ worstCell.worstPair.skewNm.toFixed(3) }}</span> nm
            ({{ cellLabel(worstCell.cell) }})
          </template>
        </p>

        <template v-if="has('pm')">
          <p
            class="sk-meta leading-relaxed"
            :class="{ 'mt-1.5': has('verdict') }"
          >
            <span class="sk-title">이 장비는</span> —
            <!-- No pick yet, and the sentence must still finish: the check half
                 can be answered while the gate roster this card's subject comes
                 from is still in flight, and every branch below assumes a
                 subject. -->
            <template v-if="!picked">
              아직 고르지 않았습니다 — 위 데이터 요청을 누르면 PM gate 와 함께 채워집니다.
            </template>
            <template v-else-if="!primary">
              그룹이 없어 판정할 수 없습니다.
            </template>
            <template v-else-if="report?.inGroup">
              1차 그룹 <span class="sk-value-num">{{ primary.n }}</span>대의 구성원 — 유지가 목표.
            </template>
            <template v-else-if="report">
              미충족 셀 <span class="sk-value-num">{{ report.blockedCells }}</span>개 ·
              최대 조정 <span class="sk-value-num">{{ maxRequiredNm.toFixed(3) }}</span> nm
              → 진입 시 그룹 <span class="sk-value-num">{{ primary.n }}→{{ primary.n + 1 }}</span>대.
            </template>
          </p>
          <p class="mt-1.5 sk-field-label leading-relaxed">
            <template v-if="parameters.length">
              측정 항목 <span class="sk-value-num">{{ parameters.join(', ') }}</span> 기준입니다.
            </template>
            <template v-else>
              측정 항목 전체를 합친 기준입니다.
            </template>
          </p>
        </template>
      </div>

      <!-- 결과 — 켠 것만, 언제나 이 순서로. 근거가 위에서 아래로 한 번씩만
           나오도록 짜인 순서라, 고른 순서가 아니라 이 순서로 그립니다
           (utils/labView normalizePanels 가 정렬을 되돌립니다). -->

      <!-- 그룹 판정 — 누가 그룹이고 누가 왜 빠졌는지. 두 카드가 한 묶음인 것은
           아래 배치도의 빨간 선이 바로 제외 카드가 말로 설명하는 그 장비쌍이기
           때문입니다. -->
      <div
        v-if="has('verdict')"
        class="grid items-stretch gap-3 lg:grid-cols-[minmax(0,1fr)_320px]"
      >
        <EbeamTttmRecommendationCard
          :primary="primary"
          :others="others"
          :tools="visibleTools"
        />
        <EbeamTttmExcludedTools
          :excluded="excluded"
          :has-group="primary !== null"
          :tools="visibleTools"
          :deviations="visibleDeviations"
          :action-limit="fleetActionLimit"
          :markers="visibleMarkers"
        />
      </div>

      <!-- 배치도 — 한 번만 그려집니다. PM 튜닝이 켜져 있으면 고른 장비를 고리로
           표시하고 그 장비가 넘긴 쌍을 표시합니다(showsPickedTool); 아니면 제외
           카드가 설명하는 쌍을 표시합니다. 예전에는 화면마다 지도를 따로 그려
           두 벌의 prop 을 유지했고, 그래서 둘이 갈라질 수 있었습니다. -->
      <div
        v-if="has('map')"
        class="grid gap-3 2xl:grid-cols-2"
      >
        <EbeamTttmFleetMap
          :fleet="visibleFleet"
          :tools="visibleTools"
          :tolerance-index="toleranceIndex"
          :group-tools="primary?.tools"
          :blocked-pair="blockedPair"
          :picked-tool="showsPickedTool ? picked : null"
          :halo-label="haloLabel"
          :pca="pca"
        />
        <EbeamTttmFleetStatus
          :deviations="visibleFleet.consensus_deviation"
          :tools="visibleTools"
          :cd="fleetCd"
        />
      </div>

      <EbeamTttmPairMatrix
        v-if="has('matrix')"
        :cells="rankedCells"
        :tools="visibleTools"
      />

      <!-- 추세 — full width: the chart is zoomable, and a zoomed span needs the
           horizontal room a half-width card could not give it. -->
      <template v-if="has('trend')">
        <EbeamTttmTrendChart
          :trend="visibleTrend"
          :markers="visibleMarkers"
        />
        <EbeamTttmMdcTimeline :history="visibleMdcHistory" />
      </template>

      <!-- PM 튜닝 — 목표와 gate. 위 튜닝할 장비 바가 이 묶음의 일부라, 이 둘만
           켤 수는 없습니다. 나란히 두는 것은 목표가 "어디로 옮길지"이고 gate 가
           "지금 만져도 되는지"라, 한 번에 같이 읽어야 하기 때문입니다. -->
      <div
        v-if="has('pm')"
        class="grid gap-3 2xl:grid-cols-2"
      >
        <!-- File is pmPlanning/Targets.vue, NOT pmPlanning/TuneTargets.vue:
             Nuxt's auto-import collapses the repeated word at the segment
             boundary (PmPlanning + TuneTargets -> PmPlanningTargets), so the
             longer file name would leave this tag rendering silently empty. -->
        <EbeamPmPlanningTargets
          :target="tuning"
          :n="primary?.n ?? 0"
          :tools="labelRefs"
        />
        <EbeamPmPlanningGateCard
          :gate="pickedGate"
          :eqp-id="picked"
        />
      </div>

      <!-- 다 껐을 때. 데이터는 와 있으므로 "요청하십시오"가 아니라 "고르십시오"
           입니다 — 빈 화면이 요청 실패로 읽히면 안 됩니다. -->
      <AppEmptyState
        v-if="!panels.length"
        title="보여 줄 분석을 고르세요."
        description="위 분석 조건의 보기에서 그릴 분석을 켜면 이미 모은 데이터로 바로 그립니다 — 다시 요청하지 않습니다."
        icon="i-lucide-layout-grid"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { windowLabel } from '~/utils/analysisWindow'
import { labViewBySlug, type LabViewSlug } from '~/utils/labView'
import { usePmPlanningApi, type FleetResponse } from '~/composables/usePmPlanningApi'
import { preferredMatrix, type FleetToday } from '~/composables/useTttmApi'
import { admissionReport, pickDefaultTool } from '~/utils/pmAdmission'
import {
  alignSkewMatrix,
  groupFromCells,
  pickPrimary,
  type GroupCell,
  type NbaGroup
} from '~/utils/tttmGrouping'
import {
  actionLimitNm,
  fractionOfLimit,
  resolveNominalCd,
  MONITOR_WAFER_CD_NM
} from '~/utils/tttmLimits'
import {
  applyTolerance,
  cellLabel,
  excludedTools,
  scoreCells,
  type CellInput
} from '~/utils/tttmCells'
import { subsetSkewMatrix, rebaseDeviations, resolveSelection } from '~/utils/tttmFleetSubset'
import { parameterPca } from '~/utils/parameterPca'
import { tuningTarget } from '~/utils/pmTuningTarget'

/**
 * The 실험실 analysis page — 장비간 스큐 and PM 플래닝, one component.
 *
 * They were two until 2026-08-30, and shared far more than they differed by:
 * one persisted scope, one check request, one analysis pipeline (cells →
 * groups → primary → excluded), four of six bars, five of six empty states.
 * The duplication was documented rather than removed — eight "same as TttmView"
 * comments — and it leaked into the product twice: the tolerance knob existed
 * on one page only, so the other captioned "tolerance 는 TTTM 페이지의 설정을
 * 따릅니다" and used the server default; and once the request went manual
 * (2026-08-28) the user had to press 데이터 요청 on each page, re-fetching the
 * same expensive check.
 *
 * `view` picks the results section, and NOTHING above the results depends on
 * it. Two routes still address this one component (see utils/labView) so the
 * slugs, the activity logging and the 실험실 entries are untouched.
 */
const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: string
  /** Which of the two routes is rendering this — `view` below resolves it. */
  slug: LabViewSlug
}>()

// What this route is called and what it opens showing.
const view = computed(() => labViewBySlug(props.slug))

// Which analyses are drawn. The route chooses the PRESET (`view.panels`); from
// there it is the user's, remembered per route. `pm` is the one that also adds
// a control — 튜닝할 장비 — because the two cards it draws are computed from
// that pick and mean nothing without it.
const { panels, has, setPanels } = useLabPanels(() => props.slug)

// The comparison scope, its recipe catalogue and the skew payload it selects.
//
// `manual`: the payload is asked for with a button and the request is narrowed
// to the picked tools — see utils/tttmRequest for why.
const {
  scoped,
  recipeId,
  parameters,
  windowWeeks,
  storedTolerance,
  recipeNames,
  recipesPending,
  recipesWithoutAPair,
  roster,
  rosterPending,
  pickedTools,
  payload,
  pending: tttmPending,
  stale,
  requestCheck,
  parameterNames,
  lock,
  scopeReady,
  onSelectedTools,
  onRecipe,
  onParameters,
  onWindow,
  onTolerance
} = useTttmScope(props.toolType, props.fab, { manual: true })

// The gate/PM half, from pm_planning. Its own request: a slow gate payload must
// not delay the map, and vice versa. Fetched under the scope's window, because
// the two payloads are joined and one label has to describe both.
//
// Fetched in BOTH views, though only PM 플래닝 draws it: the point of one page
// is that switching tabs shows an answer rather than another button. The cost
// that made the check manual is its per-run MinIO fan-out, which this query
// does not have — if it ever does, gating this on `has('pm')` is one line.
const { fetchPmPlanningFleet } = usePmPlanningApi()
const { data: pmFleet, pending: pmPending, refresh: refreshPmFleet } = useAsyncData<FleetResponse | null>(
  `pm-planning:${props.fab || 'NONE'}`,
  () => props.fab ? fetchPmPlanningFleet(props.fab, windowWeeks.value) : Promise.resolve(null),
  { immediate: false }
)

// One click, both halves. Not awaited in sequence: they are independent
// endpoints and each section should paint as soon as its own answer lands.
const request = () => {
  requestCheck()
  refreshPmFleet()
}
const pending = computed(() => tttmPending.value || pmPending.value)

const pmTools = computed(() => pmFleet.value?.tools ?? [])

// Two selections, and the difference is the on-demand request. `pickedTools`
// (from the scope) is resolved against the sem-list ROSTER and is what the
// next request will name; this one is resolved against the tools the PAYLOAD
// answered for and is what the results below are drawn from. They differ
// exactly while the payload is stale — a tool added to the picks has no data
// until the next request, and must not appear in the cards as if it had.
const answeredTools = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
const selection = computed(() => resolveSelection(answeredTools.value, scoped.value.tools))

const picked = ref<string | null>(null)

// Whether the map is drawn ABOUT a tool. The PM payload is fetched either way
// (one request feeds every panel), so `picked` is set even when nothing on
// screen is about it — ringing a tool the reader did not ask to see, and
// annotating the pair IT has to fix rather than the one the exclusion card
// explains. The subject is the panel, not the route: this used to read
// `view === 'pm-planning'`, which said the same thing only because the cards
// and the route could not be separated.
const showsPickedTool = computed(() => has('pm') && picked.value !== null)

// The working basis: the selection, plus the picked tool when PM 플래닝 is
// showing and the user picked one the group bar had deselected — its admission
// question is exactly what that view exists to answer, so it must be in the
// matrices. In 장비간 스큐 there is no such subject and the basis IS the
// selection.
//
// A caller-side union on purpose, NOT foldable into resolveSelection:
// resolveSelection treats an empty `selected` as "all", so
// resolveSelection(all, [...scoped.tools, picked]) would collapse the basis to
// the single picked tool whenever there is no explicit selection.
const basis = computed(() => {
  const p = picked.value
  if (!has('pm') || !p || !answeredTools.value.includes(p) || selection.value.includes(p)) {
    return selection.value
  }
  return [...selection.value, p]
})

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => basis.value.includes(t.eqp_id))
)
const labelRefs = computed(() => visibleTools.value.map(t => ({ eqp_id: t.eqp_id, label: t.label })))

// Pairwise data narrows exactly; consensus has to be RE-BASED on the kept
// subset, because the server computed it against the whole fleet's median.
// Pick the tier FIRST, then subset only the survivor.
//
// Equivalent because `preferredMatrix` is `direct ?? predicted` and subsetting
// never turns a matrix into null: pick-then-subset and subset-then-pick reach
// the same matrix.
const cellInputs = computed<CellInput[]>(() =>
  (payload.value?.occupied_cells ?? []).flatMap((c) => {
    const matrix = preferredMatrix(c)
    if (!matrix) return []
    return [{
      cell_id: c.cell_id,
      beam_condition: c.beam_condition,
      axis: c.axis,
      median_cd_nm: c.median_cd_nm,
      tier: c.tier,
      confidence: c.confidence,
      labels: c.labels,
      // ALIGNED, not merely subsetted. `groupFromCells` and the admission
      // report fold cells together by positional index and throw unless every
      // cell carries the same tool list in the same order — which nothing
      // upstream promises. The throw would land inside this computed, blanking
      // the page rather than a card. One shared basis makes the invariant true
      // by construction, and a tool missing from a cell arrives as nulls,
      // which is what it is.
      matrix: alignSkewMatrix(matrix, basis.value)
    }]
  })
)

const visibleFleet = computed<FleetToday>(() => ({
  matrix: subsetSkewMatrix(
    payload.value?.fleet_today.matrix ?? { tools: [], values: [] },
    basis.value
  ),
  consensus_deviation: rebaseDeviations(
    payload.value?.fleet_today.consensus_deviation ?? [],
    basis.value
  ),
  // Unchanged by subsetting: the CD is a property of what was measured, not of
  // which tools the user chose to look at. Deselecting tools re-bases the
  // deviations but must not move the limit they are judged against.
  median_cd_nm: payload.value?.fleet_today.median_cd_nm ?? null
}))

// Two deviation maps, and the difference matters. The TOOL BAR shows the
// payload's own numbers over the tools it answered for (the bar is where the
// next selection gets decided, and a tool outside the answer has nothing to
// show — `answered` keeps its badge honest); everything below reads the
// re-based ones.
const fleetDeviations = computed<Record<string, number>>(() =>
  Object.fromEntries(
    (payload.value?.fleet_today.consensus_deviation ?? []).map(d => [d.eqp_id, d.deviation])
  )
)
const visibleDeviations = computed<Record<string, number>>(() =>
  Object.fromEntries(visibleFleet.value.consensus_deviation.map(d => [d.eqp_id, d.deviation]))
)
// Resolved ONCE, for both cards that draw the PM/BM limit. `FleetStatus` used
// to re-resolve it from the same `fleet` prop while `ExcludedTools` took it as
// a prop from here — one number reached the screen by two mechanisms, so a
// change to the fallback would have moved the limit on one card and not the
// other, and the two sit two rows apart quoting each other's ±.
const fleetCd = computed(() => resolveNominalCd(visibleFleet.value.median_cd_nm))
const fleetActionLimit = computed(() => actionLimitNm(fleetCd.value.nm))

const inBasis = (eqp: string) => basis.value.includes(eqp)
const visibleTrend = computed(() => (payload.value?.trend ?? []).filter(p => inBasis(p.eqp_id)))
const visibleMarkers = computed(() =>
  (payload.value?.epoch_markers ?? []).filter(m => inBasis(m.eqp_id))
)
const visibleMdcHistory = computed(() =>
  (payload.value?.mdc_history ?? []).filter(m => inBasis(m.eqp_id))
)

// The map's placement: PCA over the picked parameters (every parameter when
// none is picked) of the tools in the basis. Null when the payload carries no
// usable profile column, and the map falls back to today's fleet matrix.
const pca = computed(() =>
  payload.value ? parameterPca(payload.value.parameter_profile, parameters.value, basis.value) : null
)

// The knob's live value. A local ref for the DRAG and the persisted scope for
// the RESULT: the slider fires on every frame, and writing the scope on each
// one would re-render every control that reads it (see setTolerance). The
// stored value wins where there is one, and the payload's own default seeds it
// otherwise — clamped here rather than at the storage layer, because the range
// is a property of the answer and only exists once one has landed.
const tolerance = ref(0.05)
watch([storedTolerance, payload], ([stored, p]) => {
  const next = stored ?? p?.current_tolerance ?? tolerance.value
  tolerance.value = p
    ? Math.min(Math.max(next, p.tolerance_range.min), p.tolerance_range.max)
    : next
}, { immediate: true })

// The knob is nanometres because the server's tolerance_range is; grouping is
// CD-relative. This is the one place that conversion happens, so every surface
// below argues in the same units.
//
// Read at the monitor-wafer CD, because that is the CD every figure in this
// feature was quoted at: the default 0.05 nm becomes "a third of the action
// limit", and means that at every pattern size rather than only at 15 nm.
const toleranceIndex = computed(() =>
  fractionOfLimit(tolerance.value, MONITOR_WAFER_CD_NM)
)

// Scored once for the surfaces that read cells — the matrix tabs, the severity
// bars, the exclusion card and the admission report. Ranking inside each
// component instead is how two of them end up disagreeing about which cell is
// worst.
//
// Split in two on purpose: `scoreCells` does the matrix walks and the sort and
// depends on the BASIS, while `applyTolerance` is the thin part that moves
// with the knob. A drag therefore re-runs only the second half.
const scoredCells = computed(() => scoreCells(cellInputs.value))
const rankedCells = computed(() => applyTolerance(scoredCells.value, toleranceIndex.value))
const worstCell = computed(() => rankedCells.value[0] ?? null)
const failingPairs = computed(() =>
  rankedCells.value.reduce((sum, c) => sum + c.failingPairs, 0)
)

// The grouping engine needs each cell's CD already resolved: a cell whose median
// CD is null falls back to the monitor wafer here rather than inside the engine.
// Reads the SCORED list, not the ranked one — nothing here depends on the knob,
// so hanging it off the per-frame half would rebuild it on every drag frame.
const groupCells = computed<GroupCell[]>(() =>
  scoredCells.value.map(c => ({
    tier: c.cell.tier,
    confidence: c.cell.confidence,
    matrix: c.matrix,
    cdNm: c.cd.nm
  }))
)

const groups = computed<NbaGroup[]>(() =>
  groupFromCells(groupCells.value, toleranceIndex.value).filter(g => g.n >= 2)
)
const primary = computed(() => pickPrimary(groups.value))
const others = computed(() =>
  groups.value.filter(g => g !== primary.value).sort((a, b) => b.n - a.n)
)
const excluded = computed(() =>
  excludedTools(basis.value, primary.value?.tools ?? [], rankedCells.value)
)

// Default pick: the tool freshest out of PM (its tuning window is now), then
// the worst-excluded tool, then the roster head — see pickDefaultTool.
//
// Gated on the pm payload having ARRIVED: the two requests race, and running
// the default off the check payload alone would pick the excluded-tool fallback
// and then stick with it (a set pick is never overwritten) even though the PM
// dates the rule actually wants were a moment away.
//
// `excluded` is read inside the callback, not watched: it exists only for the
// no-PM-date-anywhere fallback, and making it a source would force the full
// excludedTools() scan eagerly on every tolerance/cell change to guard a
// branch that almost never runs.
watch(pmFleet, () => {
  if (!pmFleet.value) return
  if (picked.value && pmTools.value.some(t => t.eqp_id === picked.value)) return
  picked.value = pickDefaultTool(
    pmTools.value.map(t => ({ eqp_id: t.eqp_id, post_pm_at: t.gate.post_pm_at })),
    excluded.value.map(e => e.eqp_id)
  )
}, { immediate: true })

const report = computed(() =>
  picked.value ? admissionReport(picked.value, primary.value?.tools ?? [], rankedCells.value) : null
)

// 튜닝 목표 — the group's centre of gravity in the SAME space the map places
// tools in, over the SAME columns (utils/pmTuningTarget shares the map's
// `usableColumns`/`profileRows`), so the table quotes the point the ring above
// it is drawn around rather than a second, similar-looking calculation.
//
// Deliberately a different axis from `report`: admission is a per-cell pairwise
// verdict, this is a per-parameter position. Both are shown, and neither is
// derived from the other.
const tuning = computed(() =>
  payload.value
    ? tuningTarget(
        payload.value.parameter_profile,
        parameters.value,
        primary.value?.tools ?? [],
        picked.value,
        toleranceIndex.value
      )
    : null
)

const maxRequiredNm = computed(() =>
  Math.max(0, ...(report.value?.cells.map(row => row.requiredNm) ?? []))
)

// The one blocked pair the map annotates, and the two views annotate different
// ones because they are answering different questions: 장비간 스큐 draws the
// lead exclusion's blocker (the pair `ExcludedTools` explains in words two
// cards up), PM 플래닝 draws the PICKED tool's worst violating pair (the one
// the tuning card leads with). Either way it is drawn only when it actually
// breached the tolerance — a tool excluded merely for a MISSING measurement has
// a blocker that passed, and a red "0.0xx nm" line through the map would assert
// a violation the number disproves.
//
// Handed on whole rather than copied field by field: re-spelling `a`/`b`/
// `skewNm` here would be a second place `PairReading`'s field names live, so a
// rename would still compile and silently drop the annotation.
const blockedPair = computed(() => {
  if (showsPickedTool.value) {
    const lead = report.value?.cells[0]
    return lead?.worst && lead.worst.skewNm > lead.thresholdNm ? lead.worst : null
  }
  const lead = excluded.value[0]
  return lead?.exceeds ? lead.blocker : null
})

const haloLabel = computed(() => {
  const group = primary.value
  if (!showsPickedTool.value || !group || !report.value || report.value.inGroup) return undefined
  return `N배화 그룹 · ${group.n}대 → ${group.n + 1}대 (튜닝 시)`
})

const pickerRows = computed(() => {
  // 그룹 membership only once a recipe has been picked. Without one the server
  // still answers — with a fleet-wide fold of every measured recipe — and the
  // results below are gated on exactly that, so a 1차 그룹 badge on the top bar
  // would be the page asserting membership in a comparison nobody chose.
  const members = new Set(scopeReady.value ? primary.value?.tools ?? [] : [])
  return pmTools.value.map(t => ({
    eqp_id: t.eqp_id,
    verdict: t.gate.verdict,
    postPmAt: t.gate.post_pm_at,
    inGroup: members.has(t.eqp_id)
  }))
})

const pickedGate = computed(() =>
  pmTools.value.find(t => t.eqp_id === picked.value)?.gate ?? null
)

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
// From the payload's echo where there is one, so the readout names the span
// the server actually gathered; the stored choice stands in while in flight.
const cadence = computed(() => windowLabel(payload.value?.window_weeks ?? windowWeeks.value))
// Empty while the scope is unset, so the bar does not headline "N배화 0" as a
// finding. MetaBar drops the whole stat strip on an empty array, and a zero
// there reads as a computed verdict rather than as "nothing computed yet".
const metaStats = computed<MetaBarStat[]>(() => {
  if (!scopeReady.value) return []
  if (has('pm')) {
    const holdCount = pmTools.value.filter(t => t.gate.verdict === 'hold').length
    return [
      { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' },
      { key: 'tools', label: '대상 장비', value: basis.value.length, tone: 'neutral' },
      { key: 'hold', label: 'Hold', value: holdCount, tone: holdCount ? 'warn' : 'neutral' }
    ]
  }
  return [
    { key: 'tools', label: '선택 장비', value: visibleTools.value.length, tone: 'neutral' },
    { key: 'cells', label: '점유 셀', value: rankedCells.value.length, tone: 'neutral' },
    { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' }
  ]
})
</script>
