<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fab}`"
      title="PM 플래닝"
      subtitle="하드웨어를 만질 기회는 PM 창뿐입니다 — 그때 N배화 그룹의 중심에 맞추도록 parameter 별 조정량을 제시합니다. N이 커질수록 서로 대체 측정할 수 있는 장비가 늘어납니다."
      :cadence="cadence"
      :as-of="asOf"
      :stats="metaStats"
    />

    <!-- The scope bar renders even on `available: false`, and while the payload
         is in flight — same rule as TttmView, and the same reason: the scope IS
         the commonest cause of an empty answer, so taking the recipe picker off
         the screen would leave the user with no way back.

         The bar is the SAME component and the same persisted entry as the TTTM
         page, tools included. Tool selection used to be readable here and
         editable only there, which is the exact complaint that made recipe and
         parameter editable from this page: a scope you have to leave the page to
         change is a scope you cannot work with. Editing either here edits it
         there — the two pages are meant to describe ONE group, so sharing is the
         safeguard, not a shortcut. -->
    <EbeamScopeBar hint="고른 recipe 의 측정 데이터로 계산합니다. 이 설정은 이 브라우저에 저장되고, TTTM · PM 플래닝 두 페이지가 함께 씁니다.">
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

    <!-- 장비 모델 그룹 — same bar, same persisted selection as TttmView, and
         since this page asks on demand too, the same roster source: sem-list,
         not the payload. The payload is what the button REQUESTS, so it cannot
         also be where the picks come from — before the first request there
         would be nothing to pick. -->
    <EbeamToolGroupBar
      :tools="roster"
      :selected="pickedTools"
      :deviations="fleetDeviations"
      :answered="answeredTools"
      :pending="rosterPending"
      hint="비교에 넣을 장비를 모델 그룹별로 고릅니다 — 고른 장비의 데이터만 서버에서 모읍니다. TTTM · PM 플래닝 두 페이지가 함께 씁니다."
      @update:selected="onSelectedTools"
    />

    <!-- 수집 기간 · 데이터 요청 — the TTTM bar verbatim, because it is the same
         request: both pages ask the same check endpoint under the same shared
         scope, and one office answer costs hundreds of MinIO GETs either way.
         It sits ABOVE 튜닝할 장비 rather than below the way TTTM's sits above
         분석 조건: that picker's rows (verdict, post_pm_at) come off the pm
         payload, so until this button is pressed there is nothing to pick.
         One click drives BOTH halves — see `request` below. -->
    <EbeamTttmRequestBar
      :window-weeks="windowWeeks"
      :tool-count="pickedTools.length"
      :has-recipe="scopeReady"
      :pending="pending"
      :stale="stale"
      :fetched-at="payload?.fetched_at ?? null"
      @update:window-weeks="onWindow"
      @request="request"
    />

    <!-- 튜닝할 장비 — 장비 모델 그룹 바로 아래입니다. 이 페이지의 주어이고 아래
         결과가 전부 이 한 대를 기준으로 계산되지만, 그 계산이 성립하려면 먼저
         비교 대상(recipe)과 장비 모델 그룹이 정해져 있어야 합니다 — 어느 집합
         안에서 고르는지가 정해지지 않은 상태의 선택은 무엇을 고르는 것인지
         말할 수 없습니다. 2026-08-27 에 분석 조건 바의 오른쪽 칸에서 페이지
         맨 위로 끌어올렸고, 2026-08-28 에 이 자리로 내렸습니다: 눈에 띄는 것과
         고를 순서가 맞는 것은 다른 문제였고, 후자가 이겼습니다.

         The pm roster is its own request and does not ride on the recipe, so
         this bar is never locked: it lists the whole fab roster whatever the
         group above selects, and picking a tool the 장비 모델 그룹 bar left out
         is a legitimate question — it is exactly the "would this one get in"
         case the page exists to answer, and `basis` below pins such a pick into
         the matrices for it. The 그룹 badge simply does not appear until there
         is a group to be in. -->
    <EbeamPmPlanningToolPicker
      :rows="pickerRows"
      :picked="picked"
      :pending="pmPending"
      :awaiting="!pmFleet"
      @update:picked="picked = $event"
    />

    <!-- 분석 조건 — same bar and same lock rule as TttmView: the parameter
         list rides on the recipe's payload, so the picker is inert until a
         recipe is picked and while its answer is unavailable. No trailing cell
         here: 튜닝할 장비 has its own bar, directly above this one. -->
    <EbeamAnalysisBar
      :lock="lock"
      note="tolerance 는 TTTM 페이지의 설정을 따릅니다."
    >
      <template #parameter>
        <EbeamScopeParameter
          :parameters="parameters"
          :parameter-names="parameterNames"
          :lock="lock"
          @update:parameters="onParameters"
        />
      </template>
    </EbeamAnalysisBar>

    <!-- 결과 — 지도 → 튜닝 목표 → gate 순. -->
    <!-- Same gate as TTTM, and deliberately the same one: the two pages describe
         one group from one scope, so a recipe that opens the results on one page
         must open them on the other. Recipe only — the parameter stays optional
         because folding every measured feature is a legitimate answer, and its
         list only exists once the recipe's payload has landed. -->
    <AppEmptyState
      v-if="!scopeReady"
      title="비교 대상을 선택하세요."
      description="위 비교 대상에서 recipe 를 고르면 그 recipe 기준으로 N배화 그룹과 튜닝 목표를 계산합니다."
      hint="recipe 를 고르면 그 측정 데이터에서 parameter 를 고를 수 있습니다 — 비워 두면 측정 항목을 모두 합쳐 판정합니다. 이 설정은 TTTM 페이지와 공유합니다."
      icon="i-lucide-mouse-pointer-click"
    />

    <!-- Gated on the tttm half only: the map and targets can paint as soon as
         the matrices arrive, and the pm-fed cards degrade cleanly while their
         request is still in flight. AND-ing both made the fast payload wait for
         the slow one. -->
    <AppLoadingState
      v-else-if="tttmPending"
      title="Fleet 데이터를 불러오는 중입니다."
    />

    <!-- Nothing asked yet — same as TttmView: the page waits for the button and
         says so where the results will appear. -->
    <AppEmptyState
      v-else-if="!payload"
      title="데이터를 요청하십시오."
      description="위 장비 모델 그룹과 수집 기간을 정한 뒤 데이터 요청을 누르면 고른 장비의 run 과 PM gate 를 서버에서 모읍니다."
      icon="i-lucide-database"
    />

    <!-- The shared empty-state shell, not a hand-rolled card: an unavailable
         payload is a legitimate answer ("nothing to compare"), which is the same
         shape of event AppEmptyState already owns. -->
    <AppEmptyState
      v-else-if="!payload?.available"
      title="튜닝 목표를 낼 수 없습니다."
      :description="payload?.summary ?? '데이터를 불러오지 못했습니다.'"
      hint="위에서 recipe · parameter 를 바꾸어 다시 계산하실 수 있습니다."
      icon="i-lucide-scale"
    />

    <!-- Same guard as TttmView: a group needs two tools to exist. -->
    <AppEmptyState
      v-else-if="basis.length < 2"
      title="비교할 장비를 2대 이상 고르세요."
      description="위 장비 모델 그룹에서 장비를 고르면 그 장비들로 N배화 그룹과 튜닝 목표를 계산합니다."
      icon="i-lucide-mouse-pointer-click"
    />

    <div
      v-else
      class="flex min-w-0 flex-col gap-3"
    >
      <!-- The payload lags the scope: the results below are still the LAST
           answer and must not be read as the current question's. Drawn, not
           hidden — same rule as TttmView. -->
      <div
        v-if="stale"
        class="rounded-[var(--sk-r-card)] border border-(--sk-warn-border) bg-(--sk-warn-soft) px-4 py-2.5 sk-meta leading-relaxed"
      >
        <span class="sk-title">조건이 바뀌었습니다</span> — 아래 결과는 마지막 요청
        <span class="font-mono tabular-nums">{{ asOf }}</span> 기준입니다. 위 데이터 요청을 누르면 반영됩니다.
      </div>

      <!-- The roll-up of what the current pick costs, directly under the bar
           that sets it. The numbers all appear again in the cards below; this
           line is what makes changing the picked tool legible without hunting
           for what moved. -->
      <div class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5">
        <p class="sk-meta leading-relaxed">
          <span class="sk-title">이 장비는</span> —
          <!-- No pick yet, and the sentence must still finish. Reachable since
               the pm half waits for 데이터 요청 (2026-08-30): arriving from TTTM
               the shared check payload draws the map straight away while the
               gate roster this card's subject comes from has not been asked
               for, and every branch below assumes a subject. -->
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
            측정 항목 <span class="sk-value-num">{{ parameters.join(', ') }}</span> 기준입니다 ·
            tolerance 는 TTTM 페이지의 설정을 따릅니다.
          </template>
          <template v-else>
            측정 항목 전체를 합친 기준입니다 · tolerance 는 TTTM 페이지의 설정을 따릅니다.
          </template>
        </p>
      </div>

      <div class="grid gap-3 2xl:grid-cols-2">
        <EbeamTttmFleetMap
          :fleet="visibleFleet"
          :tools="visibleTools"
          :tolerance-index="toleranceIndex"
          :group-tools="primary?.tools"
          :blocked-pair="blockedPair"
          :picked-tool="picked"
          :halo-label="haloLabel"
          :pca="pca"
        />
        <!-- Stacked beside the map rather than in a row of their own: the map
             is the target's definition and the table is its reading, so they
             belong in one glance, and the gate card is short enough that a
             full-width row of it alone would read as an orphan. It was in a
             320px column next to 다음 PM 후보 랭킹 until that card was
             removed (2026-08-28). -->
        <div class="flex min-w-0 flex-col gap-3">
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { windowLabel } from '~/utils/analysisWindow'
import { usePmPlanningApi, type FleetResponse } from '~/composables/usePmPlanningApi'
import { preferredMatrix, type FleetToday } from '~/composables/useTttmApi'
import { admissionReport, pickDefaultTool } from '~/utils/pmAdmission'
import { alignSkewMatrix, groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from '~/utils/tttmGrouping'
import { applyTolerance, excludedTools, scoreCells, type CellInput } from '~/utils/tttmCells'
import { fractionOfLimit, MONITOR_WAFER_CD_NM } from '~/utils/tttmLimits'
import { resolveSelection, subsetSkewMatrix, rebaseDeviations } from '~/utils/tttmFleetSubset'
import { parameterPca } from '~/utils/parameterPca'
import { tuningTarget } from '~/utils/pmTuningTarget'

const props = defineProps<{ fab: string, toolLabel: string, toolType: string }>()

// The group's inputs are the SHARED lab scope — the same persisted entry the
// TTTM page reads, through the same composable. Tools, recipe and parameter are
// all editable from here as well as from there, and editing any of them here
// edits it there: the two pages are meant to describe ONE group, so a scope this
// page could only read was a scope the user had to leave the page to change.
//
// `manual`: this page asks for the payload with a button too, and narrows the
// request to the picked tools — see utils/tttmRequest for why. The check is
// keyed the same in both pages' manual mode, so an answer requested on TTTM is
// still the answer here.
const {
  scoped,
  recipeId,
  parameters,
  windowWeeks,
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
  onWindow
} = useTttmScope(props.toolType, props.fab, { manual: true })

// The gate/PM half, from pm_planning. Independent request: a slow gate payload
// must not delay the map, and vice versa.
// Fetched under the scope's window, and re-fetched with it: the two halves of
// this page are joined and must describe one span. Which is exactly why the
// window no longer triggers it on its own — it waits for the same button, or
// the gate cards would describe a span the map above them does not.
const { fetchPmPlanningFleet } = usePmPlanningApi()
const { data: pmFleet, pending: pmPending, refresh: refreshPmFleet } = useAsyncData<FleetResponse | null>(
  `pm-planning:${props.fab || 'NONE'}`,
  () => props.fab ? fetchPmPlanningFleet(props.fab, windowWeeks.value) : Promise.resolve(null),
  { immediate: false }
)

// One click, both halves. Not awaited in sequence: they are independent
// endpoints and the map should paint as soon as its own answer lands.
const request = () => {
  requestCheck()
  refreshPmFleet()
}
const pending = computed(() => tttmPending.value || pmPending.value)

const pmTools = computed(() => pmFleet.value?.tools ?? [])

// Two selections, and the difference is the on-demand request — same split as
// TttmView. `pickedTools` (from the scope, resolved against the sem-list
// roster) is what the NEXT request will name; `selection` is resolved against
// the tools the payload actually answered for and is what the results below are
// drawn from. They differ exactly while the payload is stale.
const answeredTools = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
const selection = computed(() => resolveSelection(answeredTools.value, scoped.value.tools))

// The payload's own fleet-wide residuals, for the scope bar's dropdown rows —
// the same rule TttmView follows: a tool that is not selected has no re-based
// value to show, and this is the control where the selection gets decided.
const fleetDeviations = computed<Record<string, number>>(() =>
  Object.fromEntries(
    (payload.value?.fleet_today.consensus_deviation ?? []).map(d => [d.eqp_id, d.deviation])
  )
)

const picked = ref<string | null>(null)

// The working basis: TTTM's selection, plus the picked tool when the user
// picked one the TTTM page had deselected — its admission question is exactly
// what this page exists to answer, so it must be in the matrices.
//
// A caller-side union on purpose, NOT foldable into resolveSelection:
// resolveSelection treats an empty `selected` as "all", so
// resolveSelection(all, [...scoped.tools, picked]) would collapse the basis to
// the single picked tool whenever the TTTM page has no explicit selection.
// Pinning would have to be an explicit third parameter there; until a second
// caller needs it, it stays here.
const basis = computed(() => {
  const p = picked.value
  if (!p || !answeredTools.value.includes(p) || selection.value.includes(p)) return selection.value
  return [...selection.value, p]
})

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => basis.value.includes(t.eqp_id))
)
const labelRefs = computed(() => visibleTools.value.map(t => ({ eqp_id: t.eqp_id, label: t.label })))

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
      // ALIGNED on one shared basis — same invariant as TttmView: the fold and
      // the admission report walk cells by positional index.
      matrix: alignSkewMatrix(matrix, basis.value)
    }]
  })
)

const visibleFleet = computed<FleetToday>(() => ({
  matrix: subsetSkewMatrix(payload.value?.fleet_today.matrix ?? { tools: [], values: [] }, basis.value),
  consensus_deviation: rebaseDeviations(payload.value?.fleet_today.consensus_deviation ?? [], basis.value),
  median_cd_nm: payload.value?.fleet_today.median_cd_nm ?? null
}))

// Same placement as TttmView, over the working basis (the picked tool is
// in it even when TTTM deselected it — its position is the question).
const pca = computed(() =>
  payload.value ? parameterPca(payload.value.parameter_profile, parameters.value, basis.value) : null
)

// No tolerance knob on this page: the server's current tolerance IS the one the
// TTTM page opens on, so the group here matches the group there by default.
const toleranceIndex = computed(() =>
  fractionOfLimit(payload.value?.current_tolerance ?? 0.05, MONITOR_WAFER_CD_NM)
)

const scoredCells = computed(() => scoreCells(cellInputs.value))
const rankedCells = computed(() => applyTolerance(scoredCells.value, toleranceIndex.value))

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

const excluded = computed(() =>
  excludedTools(basis.value, primary.value?.tools ?? [], rankedCells.value)
)

// Default pick: the tool freshest out of PM (its tuning window is now), then
// the worst-excluded tool, then the roster head — see pickDefaultTool.
//
// Gated on the pm payload having ARRIVED: the two requests race, and running
// the default off the tttm payload alone would pick the excluded-tool fallback
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

// The map annotates the PICKED tool's worst violating pair — the same pair the
// tuning card leads with, so the two surfaces cannot argue about different
// numbers. Drawn only when it actually breached (same rule as TttmView).
const blockedPair = computed(() => {
  const lead = report.value?.cells[0]
  return lead?.worst && lead.worst.skewNm > lead.thresholdNm ? lead.worst : null
})

const haloLabel = computed(() => {
  const group = primary.value
  if (!group || !report.value || report.value.inGroup) return undefined
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
// Empty while the scope is unset — a "N배화 0" headline is a computed verdict,
// and nothing has been computed yet. MetaBar drops the strip on an empty array.
const metaStats = computed<MetaBarStat[]>(() => {
  if (!scopeReady.value) return []
  const holdCount = pmTools.value.filter(t => t.gate.verdict === 'hold').length
  return [
    { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' },
    { key: 'tools', label: '대상 장비', value: basis.value.length, tone: 'neutral' },
    { key: 'hold', label: 'Hold', value: holdCount, tone: holdCount ? 'warn' : 'neutral' }
  ]
})
</script>
