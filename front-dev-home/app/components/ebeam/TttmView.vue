<template>
  <div class="space-y-4">
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

    <template v-else>
      <EbeamTttmFleetPicker
        :tools="payload.tools"
        :selected="selectedTools"
        :recipe-id="recipeId"
        :recipe-names="recipeNames"
        :recipes-pending="recipesPending"
        @update:selected="onSelectedTools"
        @update:recipe-id="onRecipe"
      />

      <div class="dashboard-surface rounded-2xl p-4">
        <EbeamTttmToleranceKnob
          v-model="tolerance"
          :range="payload.tolerance_range"
          :tolerance-index="toleranceIndex"
        />
      </div>

      <EbeamTttmRecommendationCard
        :primary="primary"
        :others="others"
        :tools="visibleTools"
      />

      <EbeamTttmProductionChip :corroboration="payload.production_corroboration" />

      <EbeamTttmPairMatrix
        :cells="visibleCells"
        :tools="visibleTools"
        :tolerance-index="toleranceIndex"
      />

      <EbeamTttmFleetStatus
        :fleet="visibleFleet"
        :tools="visibleTools"
      />
      <EbeamTttmFleetMap
        :fleet="visibleFleet"
        :tools="visibleTools"
        :tolerance-index="toleranceIndex"
      />
      <EbeamTttmTrendChart
        :trend="visibleTrend"
        :markers="visibleMarkers"
      />
      <EbeamTttmMdcTimeline :history="visibleMdcHistory" />
    </template>
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
import { fractionOfLimit, resolveNominalCd, MONITOR_WAFER_CD_NM } from '~/utils/tttmLimits'
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

// occupied cells → GroupCell[] (direct matrix preferred, else predicted).
// Each carries its own CD, already resolved: a cell whose median CD is null
// falls back to the monitor wafer here rather than inside the engine.
const groupCells = computed<GroupCell[]>(() =>
  visibleCells.value
    .map((c) => {
      const matrix = preferredMatrix(c)
      return matrix
        ? {
            tier: c.tier,
            confidence: c.confidence,
            matrix,
            cdNm: resolveNominalCd(c.median_cd_nm).nm
          }
        : null
    })
    .filter((c): c is GroupCell => c !== null)
)

const groups = computed<NbaGroup[]>(() =>
  groupFromCells(groupCells.value, toleranceIndex.value).filter(g => g.n >= 2)
)
const primary = computed(() => pickPrimary(groups.value))
const others = computed(() =>
  groups.value.filter(g => g !== primary.value).sort((a, b) => b.n - a.n)
)

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'tools', label: '장비 그룹', value: visibleTools.value.length, tone: 'neutral' },
  { key: 'cells', label: '점유 셀', value: visibleCells.value.length, tone: 'neutral' },
  { key: 'n', label: '최대 N배화', value: primary.value?.n ?? 0, tone: 'ok' }
])
</script>
