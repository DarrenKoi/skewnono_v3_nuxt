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
      <div class="dashboard-surface rounded-2xl p-4">
        <EbeamSkewCheckToleranceKnob
          v-model="tolerance"
          :range="payload.tolerance_range"
        />
      </div>

      <EbeamSkewCheckRecommendationCard
        :primary="primary"
        :others="others"
        :tools="payload.tools"
      />

      <EbeamSkewCheckProductionChip :corroboration="payload.production_corroboration" />

      <EbeamSkewCheckPairMatrix
        :cells="payload.occupied_cells"
        :tools="payload.tools"
        :tolerance="tolerance"
      />

      <EbeamSkewCheckFleetStatus
        :fleet="payload.fleet_today"
        :tools="payload.tools"
      />
      <EbeamSkewCheckTrendChart
        :trend="payload.trend"
        :markers="payload.epoch_markers"
      />
      <EbeamSkewCheckMdcTimeline :history="payload.mdc_history" />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from '~/utils/skewGrouping'

const props = defineProps<{ fab: string, toolLabel: string, toolType: string }>()

const { useSkewCheck } = useSkewCheckApi()
const { data: payload, pending } = useSkewCheck(props.toolType, props.fab)

const tolerance = ref(0.05)
watch(payload, (p) => {
  if (p) tolerance.value = p.current_tolerance
}, { immediate: true })

// occupied cells → GroupCell[] (direct matrix preferred, else predicted).
const groupCells = computed<GroupCell[]>(() =>
  (payload.value?.occupied_cells ?? [])
    .map((c) => {
      const matrix = c.direct_skew_matrix ?? c.predicted_skew_matrix
      return matrix ? { tier: c.tier, confidence: c.confidence, matrix } : null
    })
    .filter((c): c is GroupCell => c !== null)
)

const groups = computed<NbaGroup[]>(() =>
  groupFromCells(groupCells.value, tolerance.value).filter(g => g.n >= 2)
)
const primary = computed(() => pickPrimary(groups.value))
const others = computed(() =>
  groups.value.filter(g => g !== primary.value).sort((a, b) => b.n - a.n)
)

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'tools', label: '함대', value: payload.value?.tools.length ?? 0, tone: 'neutral' },
  { key: 'cells', label: '점유 셀', value: payload.value?.occupied_cells.length ?? 0, tone: 'neutral' },
  { key: 'n', label: '최대 N배화', value: primary.value?.n ?? 0, tone: 'ok' }
])
</script>
