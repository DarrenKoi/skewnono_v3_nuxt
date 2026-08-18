<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fab}`"
      title="장비간 스큐 관리"
      subtitle="Recipe가 점유하는 셀에서 서로 잘 맞는(N배화) 측정 장비 조합을 추천합니다."
      cadence="1주 윈도우"
      :as-of="asOf"
      :stats="metaStats"
    />

    <AppLoadingState
      v-if="pending"
      title="장비간 스큐 데이터를 불러오는 중입니다."
    />
    <!-- The rail renders WHATEVER the payload says, including `available:
         false`. It used to be inside the same `v-else` as the results, so an
         empty answer took the controls down with it — and the commonest cause
         of an empty answer is the scope itself (a recipe with no pair, a
         parameter nobody measured, a stored pick that no longer applies). The
         one control that could fix it was the one thing removed from the
         screen. Only the RESULTS column collapses now. -->
    <div
      v-else
      class="grid items-start gap-3 xl:grid-cols-[392px_minmax(0,1fr)]"
    >
      <!-- 조작 레일 — 스크롤해도 따라옵니다. 결과 쪽에는 컨트롤이 하나도 없고,
           레일에는 결과가 하나도 없습니다. -->
      <div class="flex flex-col gap-3 xl:sticky xl:top-2">
        <EbeamTttmScopePanel
          :tools="payload?.tools ?? []"
          :selected="selectedTools"
          :deviations="fleetDeviations"
          :recipe-id="recipeId"
          :recipe-names="recipeNames"
          :recipes-pending="recipesPending"
          :parameter="parameter"
          :parameter-names="parameterNames"
          :parameters-pending="parametersPending"
          :parameters-error="parametersError"
          :recipes-without-a-pair="recipesWithoutAPair"
          @update:parameter="onParameter"
          @update:selected="onSelectedTools"
          @update:recipe-id="onRecipe"
        >
          <!-- Slotted, not passed down: the knob fires on every drag frame, and
               a prop through ScopePanel would re-render all seven model-group
               dropdowns with it. -->
          <template #tolerance>
            <EbeamTttmToleranceKnob
              v-if="payload"
              v-model="tolerance"
              :range="payload.tolerance_range"
              :tolerance-index="toleranceIndex"
            />
          </template>
        </EbeamTttmScopePanel>

        <!-- What the knob and the picks currently cost, in one line. The
             numbers all appear again below in their own cards; this is the
             roll-up that makes dragging the slider legible without scrolling
             the results column to find out what moved. -->
        <!-- Hidden rather than zeroed when nothing was computed: "점유 셀 0개 ·
             불합격 0쌍" reads as a clean result, which is the opposite of what
             an unavailable payload means. -->
        <div
          v-if="payload?.available"
          class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5"
        >
          <p class="sk-title">
            이 설정에서
          </p>
          <!-- `.sk-meta` for the sentence and `.sk-value-num` for each number,
               per DESIGN.md §Colors' litmus — "value → ink; label → ink-muted".
               This line was entirely `.sk-field-label`, i.e. ink-SUBTLE, which
               the same section reserves for disabled/de-emphasised text; the
               three numbers it exists to report were the faintest thing on the
               rail, and fainter than the identical count in the picker above.
               Both classes sit at 12px, so the numerals gain ink and tabular
               figures without breaking the line's rhythm. -->
          <p class="mt-1.5 sk-meta leading-relaxed">
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
      </div>

      <!-- 결과 — 판정 → 지도·셀 → 행렬 → 잔차·트렌드 순으로, 근거가 위에서
           아래로 한 번씩만 나옵니다. -->
      <div class="flex min-w-0 flex-col gap-3">
        <div
          v-if="!payload?.available"
          class="dashboard-surface rounded-[var(--sk-r-card)] p-4"
        >
          <p class="sk-title text-(--sk-bad)">
            비교할 결과가 없습니다
          </p>
          <p class="mt-1.5 sk-meta leading-relaxed">
            {{ payload?.summary ?? '데이터를 불러오지 못했습니다.' }}
          </p>
          <p class="mt-1.5 sk-field-label leading-relaxed">
            왼쪽에서 recipe · parameter · 장비를 바꾸어 다시 계산하실 수 있습니다.
          </p>
        </div>

        <template v-else>
          <div class="grid items-stretch gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
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

          <div class="grid gap-3 2xl:grid-cols-2">
            <EbeamTttmFleetMap
              :fleet="visibleFleet"
              :tools="visibleTools"
              :tolerance-index="toleranceIndex"
              :group-tools="primary?.tools"
              :blocked-pair="blockedPair"
            />
            <EbeamTttmCellSeverityList
              :cells="rankedCells"
              :tools="visibleTools"
            />
          </div>

          <EbeamTttmPairMatrix
            :cells="rankedCells"
            :tools="visibleTools"
          />

          <div class="grid gap-3 2xl:grid-cols-2">
            <EbeamTttmFleetStatus
              :deviations="visibleFleet.consensus_deviation"
              :tools="visibleTools"
              :cd="fleetCd"
            />
            <EbeamTttmTrendChart
              :trend="visibleTrend"
              :markers="visibleMarkers"
            />
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <EbeamTttmMdcTimeline :history="visibleMdcHistory" />
            <EbeamTttmProductionChip :corroboration="payload.production_corroboration" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
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
import { preferredMatrix, type FleetToday } from '~/composables/useTttmApi'

const props = defineProps<{ fab: string, toolLabel: string, toolType: string }>()

// The comparison scope and its two catalogues, shared verbatim with pm-tune —
// see useTttmScope for why this is one composable rather than wiring per page.
const {
  scoped,
  recipeId,
  parameter,
  recipeNames,
  recipesPending,
  recipesWithoutAPair,
  parameterNames,
  parametersPending,
  parametersError,
  onSelectedTools,
  onRecipe,
  onParameter
} = useTttmScope(props.toolType, props.fab)

const { useTttmCheck } = useTttmApi()
const { data: payload, pending } = useTttmCheck(
  props.toolType,
  props.fab,
  () => recipeId.value,
  () => parameter.value
)

const allToolIds = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
// Stored selection resolved against the fleet the server actually returned:
// empty means all, and ids that no longer exist are dropped.
const selectedTools = computed(() => resolveSelection(allToolIds.value, scoped.value.tools))

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => selectedTools.value.includes(t.eqp_id))
)

// Pairwise data narrows exactly; consensus has to be RE-BASED on the kept
// subset, because the server computed it against the whole fleet's median.
// Pick the tier FIRST, then subset only the survivor. Subsetting both matrices
// and choosing afterwards narrowed one that was about to be discarded, and left
// an intermediate that was neither the API's `SkewCondition` nor the engine's
// `CellInput` for a second computed to re-copy field by field.
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
      // ALIGNED, not merely subsetted. `groupFromCells` folds the cells together
      // by positional index and throws unless every cell carries the same tool
      // list in the same order — which nothing upstream promises. The throw
      // would land inside this computed, blanking the page rather than a card.
      // One shared basis makes the invariant true by construction, and a tool
      // missing from a cell arrives as nulls, which is what it is.
      matrix: alignSkewMatrix(matrix, selectedTools.value)
    }]
  })
)

const visibleFleet = computed<FleetToday>(() => ({
  matrix: subsetSkewMatrix(
    payload.value?.fleet_today.matrix ?? { tools: [], values: [] },
    selectedTools.value
  ),
  consensus_deviation: rebaseDeviations(
    payload.value?.fleet_today.consensus_deviation ?? [],
    selectedTools.value
  ),
  // Unchanged by subsetting: the CD is a property of what was measured, not of
  // which tools the user chose to look at. Deselecting tools re-bases the
  // deviations but must not move the limit they are judged against.
  median_cd_nm: payload.value?.fleet_today.median_cd_nm ?? null
}))

// Two deviation maps, and the difference matters. The PICKER shows the payload's
// own fleet-wide numbers, because a tool that is not selected has no re-based
// value to show and the picker is where the selection gets decided; everything
// below the picker reads the re-based ones.
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

const inSelection = (eqp: string) => selectedTools.value.includes(eqp)
const visibleTrend = computed(() => (payload.value?.trend ?? []).filter(p => inSelection(p.eqp_id)))
const visibleMarkers = computed(() =>
  (payload.value?.epoch_markers ?? []).filter(m => inSelection(m.eqp_id))
)
const visibleMdcHistory = computed(() =>
  (payload.value?.mdc_history ?? []).filter(m => inSelection(m.eqp_id))
)

const tolerance = ref(0.05)
watch(payload, (p) => {
  if (p) tolerance.value = p.current_tolerance
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

// Scored once for the three surfaces that read cells — the matrix tabs, the
// severity bars and the exclusion card. Ranking inside each component instead is
// how two of them end up disagreeing about which cell is worst.
//
// Split in two on purpose: `scoreCells` does the matrix walks and the sort and
// depends on the SELECTION, while `applyTolerance` is the thin part that moves
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
  excludedTools(selectedTools.value, primary.value?.tools ?? [], rankedCells.value)
)

// The one blocked pair the map annotates: the lead exclusion's blocker, which
// is the same pair `ExcludedTools` explains in words two cards up. Drawn only
// when it actually breached the tolerance — a tool excluded merely for a
// MISSING measurement has a blocker that passed, and a red "0.0xx nm" line
// through the map would assert a violation the number disproves.
// Handed on whole rather than copied field by field: re-spelling `a`/`b`/
// `skewNm` here would be a second place `PairReading`'s field names live, so a
// rename would still compile and silently drop the annotation.
const blockedPair = computed(() => {
  const lead = excluded.value[0]
  return lead?.exceeds ? lead.blocker : null
})

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'tools', label: '선택 장비', value: visibleTools.value.length, tone: 'neutral' },
  { key: 'cells', label: '점유 셀', value: rankedCells.value.length, tone: 'neutral' },
  { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' }
])
</script>
