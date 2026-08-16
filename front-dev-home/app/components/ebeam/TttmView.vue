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
    <div
      v-else-if="!payload?.available"
      class="text-sm text-(--sk-bad)"
    >
      {{ payload?.summary ?? '데이터가 없습니다.' }}
    </div>

    <div
      v-else
      class="grid items-start gap-3 xl:grid-cols-[392px_minmax(0,1fr)]"
    >
      <!-- 조작 레일 — 스크롤해도 따라옵니다. 결과 쪽에는 컨트롤이 하나도 없고,
           레일에는 결과가 하나도 없습니다. -->
      <div class="flex flex-col gap-3 xl:sticky xl:top-2">
        <EbeamTttmScopePanel
          :tools="payload.tools"
          :selected="selectedTools"
          :deviations="fleetDeviations"
          :recipe-id="recipeId"
          :recipe-names="recipeNames"
          :recipes-pending="recipesPending"
          :tolerance="tolerance"
          :range="payload.tolerance_range"
          :tolerance-index="toleranceIndex"
          @update:selected="onSelectedTools"
          @update:recipe-id="onRecipe"
          @update:tolerance="tolerance = $event"
        />

        <!-- What the knob and the picks currently cost, in one line. The
             numbers all appear again below in their own cards; this is the
             roll-up that makes dragging the slider legible without scrolling
             the results column to find out what moved. -->
        <div class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5">
          <p class="sk-title">
            이 설정에서
          </p>
          <p class="mt-1.5 sk-field-label leading-relaxed">
            <!-- "셀 합계" is load-bearing: the matrix card below reports the
                 failing pairs of ONE cell, and the two numbers differ by design.
                 Unlabelled they read as the same count disagreeing with itself. -->
            점유 셀 {{ rankedCells.length }}개 · 불합격 장비쌍 {{ failingPairs }}쌍 (셀 합계)
            <template v-if="worstCell?.worstPair">
              · 최악 {{ worstCell.worstPair.skewNm.toFixed(3) }} nm ({{ cellLabel(worstCell.cell) }})
            </template>
          </p>
        </div>
      </div>

      <!-- 결과 — 판정 → 지도·셀 → 행렬 → 잔차·트렌드 순으로, 근거가 위에서
           아래로 한 번씩만 나옵니다. -->
      <div class="flex min-w-0 flex-col gap-3">
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
            :fleet="visibleFleet"
            :tools="visibleTools"
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import {
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
import { cellLabel, excludedTools, rankCells, type CellInput } from '~/utils/tttmCells'
import { subsetSkewMatrix, rebaseDeviations, resolveSelection } from '~/utils/tttmFleetSubset'
import { preferredMatrix, type SkewCondition, type FleetToday } from '~/composables/useTttmApi'

const props = defineProps<{ fab: string, toolLabel: string, toolType: string }>()

const settings = useTttmSettings()
const scoped = computed(() => settings.read(props.toolType, props.fab))
const recipeId = computed(() => scoped.value.recipeId)

const { useTttmCheck } = useTttmApi()
const { data: payload, pending } = useTttmCheck(props.toolType, props.fab, () => recipeId.value)

// Recipe catalogue for the picker. Its own request, so a slow catalogue never
// delays the skew payload the page is actually about.
const { fetchRecipeList } = useRecipeSearchApi()
const { data: recipeList, pending: recipesPending } = useAsyncData(
  `tttm-recipes:${props.toolType}:${props.fab}`,
  () => fetchRecipeList({ toolType: props.toolType as 'cd-sem' | 'hv-sem', fabNames: [props.fab] })
)
const recipeNames = computed(() =>
  [...new Set((recipeList.value?.rows ?? []).map(row => row.recipe_name))].sort()
)

const allToolIds = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
// Stored selection resolved against the fleet the server actually returned:
// empty means all, and ids that no longer exist are dropped.
const selectedTools = computed(() => resolveSelection(allToolIds.value, scoped.value.tools))

const onSelectedTools = (next: string[]) => settings.setTools(props.toolType, props.fab, next)
const onRecipe = (next: string | null) => settings.setRecipe(props.toolType, props.fab, next)

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => selectedTools.value.includes(t.eqp_id))
)

// Pairwise data narrows exactly; consensus has to be RE-BASED on the kept
// subset, because the server computed it against the whole fleet's median.
const visibleCells = computed<SkewCondition[]>(() =>
  (payload.value?.occupied_cells ?? []).map(cell => ({
    ...cell,
    direct_skew_matrix: cell.direct_skew_matrix
      ? subsetSkewMatrix(cell.direct_skew_matrix, selectedTools.value)
      : null,
    predicted_skew_matrix: cell.predicted_skew_matrix
      ? subsetSkewMatrix(cell.predicted_skew_matrix, selectedTools.value)
      : null
  }))
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
const fleetActionLimit = computed(() =>
  actionLimitNm(resolveNominalCd(visibleFleet.value.median_cd_nm).nm)
)

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

// Cells reduced to the one matrix each reads through, then ranked once for the
// three surfaces that need them — the matrix tabs, the severity bars and the
// exclusion card. Ranking in each component instead is how two of them end up
// disagreeing about which cell is worst.
// Built field by field rather than spread: CellInput is deliberately narrower
// than SkewCondition — it carries the ONE matrix the cell reads through, so no
// surface downstream can quietly re-pick between the direct and predicted tiers.
const cellInputs = computed<CellInput[]>(() =>
  visibleCells.value.flatMap((c) => {
    const matrix = preferredMatrix(c)
    if (!matrix) return []
    return [{
      cell_id: c.cell_id,
      beam_condition: c.beam_condition,
      axis: c.axis,
      cd_band: c.cd_band,
      median_cd_nm: c.median_cd_nm,
      tier: c.tier,
      confidence: c.confidence,
      labels: c.labels,
      matrix
    }]
  })
)
const rankedCells = computed(() => rankCells(cellInputs.value, toleranceIndex.value))
const worstCell = computed(() => rankedCells.value[0] ?? null)
const failingPairs = computed(() =>
  rankedCells.value.reduce((sum, c) => sum + c.failingPairs, 0)
)

// The grouping engine needs each cell's CD already resolved: a cell whose median
// CD is null falls back to the monitor wafer here rather than inside the engine.
const groupCells = computed<GroupCell[]>(() =>
  rankedCells.value.map(c => ({
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

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'tools', label: '선택 장비', value: visibleTools.value.length, tone: 'neutral' },
  { key: 'cells', label: '점유 셀', value: rankedCells.value.length, tone: 'neutral' },
  { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' }
])
</script>
