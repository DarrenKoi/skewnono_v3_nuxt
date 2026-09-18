<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fab}`"
      title="장비간 스큐 관리"
      subtitle="선택한 레시피에서 서로 허용 오차 안에 맞는 장비 그룹을 추천합니다."
      :cadence="cadence"
      :as-of="asOf"
      :stats="metaStats"
    />

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
    <EbeamScopeBar hint="비교할 레시피를 선택합니다.">
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
      :window-label="cadence"
      :answered="answeredTools"
      :pending="rosterPending"
      hint="비교할 장비를 모델별로 선택합니다."
      @update:selected="onSelectedTools"
    />

    <EbeamRequestBar
      :window-weeks="windowWeeks"
      :tool-count="pickedTools.length"
      :has-recipe="scopeReady"
      :pending="tttmPending"
      :stale="stale"
      :fetched-at="payload?.fetched_at ?? null"
      @update:window-weeks="onWindow"
      @request="requestCheck"
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

      <template #panels>
        <EbeamLabPanelPicker
          :panels="panels"
          @update:panels="setPanels"
        />
      </template>

      <template
        v-if="!has('map') && payload"
        #trailing="{ disabled }"
      >
        <EbeamToleranceKnob
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
         chose. One gate for every panel: they describe one group from one scope,
         so a recipe that opens one card opens them all. The parameter stays
         optional: folding every measured
         feature is a legitimate answer, and its list only exists once this
         payload has landed. -->
    <AppEmptyState
      v-if="!scopeReady"
      title="비교 대상을 선택하세요."
      description="레시피를 선택한 뒤 장비와 수집 기간을 정합니다."
      icon="i-lucide-mouse-pointer-click"
    />

    <AppLoadingState
      v-else-if="tttmPending"
      title="측정 데이터를 불러오는 중입니다."
    />

    <!-- Nothing asked yet. The old pages fetched on load; this one waits for
         the button, and says so where the results will appear. -->
    <AppEmptyState
      v-else-if="!payload"
      title="데이터를 요청하십시오."
      description="장비와 수집 기간을 정한 뒤 데이터 요청을 누릅니다."
      icon="i-lucide-database"
    />

    <!-- The shared empty-state shell, not a hand-rolled card: an unavailable
         payload is a legitimate answer ("nothing to compare"), which is the same
         shape of event AppEmptyState already owns. -->
    <AppEmptyState
      v-else-if="!payload?.available"
      title="계산할 결과가 없습니다."
      :description="payload?.summary ?? '데이터를 불러오지 못했습니다.'"
      hint="레시피나 장비를 바꾸어 다시 요청할 수 있습니다."
      icon="i-lucide-scale"
    />

    <!-- One tool is not a comparison. The tool bar lets the selection drop
         to one or none (that is what 해제 means), and this is where the page
         says so instead of drawing empty cards. -->
    <AppEmptyState
      v-else-if="basis.length < 2"
      title="비교할 장비를 2대 이상 고르세요."
      description="선택한 장비 사이의 스큐를 비교합니다."
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
      <div
        v-if="has('verdict')"
        class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5"
      >
        <!-- `.sk-meta` for the sentence and `.sk-value-num` for each number, per
             DESIGN.md §Colors' litmus — "value → ink; label → ink-muted". -->
        <p
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
      </div>

      <!-- 결과 — 켠 것만, 언제나 이 순서로. 근거가 위에서 아래로 한 번씩만
           나오도록 짜인 순서라, 고른 순서가 아니라 이 순서로 그립니다
           (utils/labView normalizePanels 가 정렬을 되돌립니다). -->

      <EbeamTttmRecommendationCard
        v-if="has('verdict')"
        :primary="primary"
        :others="others"
        :tools="visibleTools"
      />

      <div
        v-if="has('map')"
        class="grid min-w-0 gap-3 lg:grid-cols-2"
      >
        <EbeamTttmFleetMap
          v-model:picked-tool="picked"
          :fleet="visibleFleet"
          :tools="visibleTools"
          :tolerance-index="toleranceIndex"
          :group-tools="primary?.tools"
          :blocked-pair="blockedPair"
          :pca="pca"
        >
          <EbeamToleranceKnob
            v-model="tolerance"
            :range="payload.tolerance_range"
            :tolerance-index="toleranceIndex"
            :disabled="lock !== null && lock !== 'loading'"
            @commit="onTolerance"
          />
        </EbeamTttmFleetMap>
        <EbeamPmPlanningTargets
          :target="tuning"
          :picked-tool="picked"
          :tools="visibleTools"
        />
      </div>

      <div
        v-if="has('map') || has('verdict')"
        class="grid min-w-0 gap-3"
        :class="{ 'lg:grid-cols-[minmax(0,1fr)_320px]': has('map') && has('verdict') }"
      >
        <EbeamTttmFleetStatus
          v-if="has('map')"
          :deviations="windowDeviations"
          :tools="visibleTools"
          :cd="fleetCd"
          :window-label="cadence"
        />
        <EbeamTttmExcludedTools
          v-if="has('verdict')"
          :excluded="excluded"
          :has-group="primary !== null"
          :tools="visibleTools"
          :deviations="visibleDeviations"
          :action-limit="fleetActionLimit"
          :markers="visibleMarkers"
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

      <!-- 다 껐을 때. 데이터는 와 있으므로 "요청하십시오"가 아니라 "고르십시오"
           입니다 — 빈 화면이 요청 실패로 읽히면 안 됩니다. -->
      <AppEmptyState
        v-if="!panels.length"
        title="보여 줄 분석을 고르세요."
        description="분석 조건의 보기에서 표시할 분석을 선택합니다."
        icon="i-lucide-layout-grid"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { preferredMatrix } from '~/composables/useTttmApi'
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
import { subsetSkewMatrix, rebaseDeviations, windowResiduals, resolveSelection } from '~/utils/tttmFleetSubset'
import { parameterPca } from '~/utils/parameterPca'
import { tuningTarget } from '~/utils/pmTuningTarget'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: string
}>()

const { panels, has, setPanels } = useLabPanels()

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

// Two selections, and the difference is the on-demand request. `pickedTools`
// (from the scope) is resolved against the sem-list ROSTER and is what the
// next request will name; this one is resolved against the tools the PAYLOAD
// answered for and is what the results below are drawn from. They differ
// exactly while the payload is stale — a tool added to the picks has no data
// until the next request, and must not appear in the cards as if it had.
const answeredTools = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
const selection = computed(() => resolveSelection(answeredTools.value, scoped.value.tools))

const picked = ref<string | null>(null)

const basis = selection
watch(basis, (tools) => {
  if (picked.value && !tools.includes(picked.value)) picked.value = null
})

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => basis.value.includes(t.eqp_id))
)

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
      // ALIGNED, not merely subsetted. `groupFromCells` folds cells by positional index and throws unless every
      // cell carries the same tool list in the same order — which nothing
      // upstream promises. The throw would land inside this computed, blanking
      // the page rather than a card. One shared basis makes the invariant true
      // by construction, and a tool missing from a cell arrives as nulls,
      // which is what it is.
      matrix: alignSkewMatrix(matrix, basis.value)
    }]
  })
)

const visibleFleet = computed(() => ({
  matrix: subsetSkewMatrix(
    payload.value?.fleet_today.matrix ?? { tools: [], values: [] },
    basis.value
  ),
  // Unchanged by subsetting: the CD is a property of what was measured, not of
  // which tools the user chose to look at. Deselecting tools re-bases the
  // deviations but must not move the limit they are judged against.
  median_cd_nm: payload.value?.fleet_today.median_cd_nm ?? null
}))

// Median of each tool's daily residuals in the answered window, then
// re-centred on the visible basis. The picker uses the full answered basis.
const residuals = computed(() => windowResiduals(payload.value?.trend ?? []))
const windowDeviations = computed(() => rebaseDeviations(residuals.value, basis.value))
const fleetDeviations = computed<Record<string, number>>(() =>
  Object.fromEntries(rebaseDeviations(residuals.value, answeredTools.value).map(d => [d.eqp_id, d.deviation]))
)
const visibleDeviations = computed<Record<string, number>>(() =>
  Object.fromEntries(windowDeviations.value.map(d => [d.eqp_id, d.deviation]))
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
// bars and the exclusion card. Ranking inside each
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

// Same parameter space as the map. The basis goes along so that, when the
// knob leaves no group, the card can fall back to the COMPARED tools rather
// than to everything the profile knows about (a deselected tool must not
// quietly rejoin as a reference).
const tuning = computed(() =>
  payload.value
    ? tuningTarget(
        payload.value.parameter_profile,
        parameters.value,
        primary.value?.tools ?? [],
        basis.value,
        picked.value,
        toleranceIndex.value
      )
    : null
)

const blockedPair = computed(() => {
  const lead = excluded.value[0]
  return lead?.exceeds ? lead.blocker : null
})

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
// From the payload's echo where there is one, so the readout names the span
// the server actually gathered; the stored choice stands in while in flight.
const cadence = computed(() => `최근 ${payload.value?.window_weeks ?? windowWeeks.value}주`)
// Empty while the scope is unset, so the bar does not headline "N배화 0" as a
// finding. MetaBar drops the whole stat strip on an empty array, and a zero
// there reads as a computed verdict rather than as "nothing computed yet".
const metaStats = computed<MetaBarStat[]>(() => {
  if (!scopeReady.value) return []
  return [
    { key: 'tools', label: '선택 장비', value: visibleTools.value.length, tone: 'neutral' },
    { key: 'cells', label: '점유 셀', value: rankedCells.value.length, tone: 'neutral' },
    { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' }
  ]
})
</script>
