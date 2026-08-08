<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="status === 'pending' && !equipmentRows.length"
      title="장비별 데이터를 불러오는 중입니다."
    />
    <div
      v-else-if="!equipmentRows.length"
      class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-inbox"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 sk-body">
        이 기간에 측정한 장비가 없습니다.
      </p>
      <p class="mt-1 sk-meta">
        기간을 넓히거나 다른 fab을 선택해보세요.
      </p>
    </div>

    <template v-else>
      <EbeamFailIssueFleetTable
        :rows="equipmentRows"
        :percentiles="percentiles"
        :peer-group-comparable="peerGroupComparable"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        :section="section"
        @update:selected="selected = $event"
      />

      <EbeamFailIssueEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
        :section="section"
      />
      <div
        v-else
        class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-10 text-center"
      >
        <UIcon
          name="i-lucide-mouse-pointer-click"
          class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
        />
        <p class="mt-2 sk-body">
          장비를 선택해주세요
        </p>
        <p class="mt-1 sk-meta">
          위 표에서 최대 {{ MAX_COMPARE_EQPS }}대까지 체크하면 추이와 레시피 구성을 비교합니다.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { MAX_COMPARE_EQPS } from '~/utils/analyticsLimits'
import { isPeerGroupComparable } from '~/utils/equipmentSignals'
import { useFailIssueApi, type FailIssueToolType } from '~/composables/useFailIssueApi'

const props = defineProps<{
  fabs: string[]
  toolType: FailIssueToolType
  dateRange: { start: string, end: string }
  section: 'align' | 'meas'
}>()

const { fetchEquipments } = useFailIssueApi()

const selected = ref<string[]>([])

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined
}))

// section 은 키에 없습니다 — 응답이 align·meas 두 축을 다 담고 있으므로
// 탭을 오가도 재요청이 필요 없습니다(설계 2절의 "응답 분할" 결정).
const cacheKey = computed(
  () => `fail-issue-equipments:${queryParams.value.toolType}`
    + `:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchEquipments(queryParams.value),
  { watch: [cacheKey] }
)

// 조회 범위가 바뀌면 선택을 비웁니다. 범위 밖 장비를 선택한 채로 두면
// 빈 비교 패널이 남습니다 (디바이스별의 resetKey 패턴과 같은 이유).
watch(cacheKey, () => {
  selected.value = []
})

const equipmentRows = computed(() => data.value?.equipments ?? [])
const percentiles = computed(() => data.value?.fleet.percentiles ?? {})

// 배지는 또래 집단이 한 fab일 때만 장비를 가리킵니다. 응답이 에코하는
// `fab_names`가 아니라 **실제로 돌아온 행**의 fab을 세는 이유는, fab 없이
// 조회하면 에코가 빈 목록인 채로 데이터는 전 fab을 덮기 때문입니다. 선택한
// fab 중 한 곳에 측정이 하나도 없어 결과적으로 한 fab만 남는 경우도 행을
// 세는 쪽이 맞습니다.
const peerGroupComparable = computed(() => isPeerGroupComparable(equipmentRows.value))

const selectedRows = computed(
  () => equipmentRows.value.filter(row => selected.value.includes(row.eqp_id))
)
</script>
