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
      <EbeamRecipeTatFleetTable
        :rows="equipmentRows"
        :percentiles="percentiles"
        :peer-group-comparable="peerGroupComparable"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        @update:selected="selected = $event"
        @download="downloadFleetCsv"
        @copy="copyFleetTable"
      />

      <EbeamRecipeTatEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
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
          위 표에서 최대 {{ MAX_COMPARE_EQPS }}대까지 체크하면 트렌드와 레시피 구성을 비교합니다.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { MAX_COMPARE_EQPS } from '~/utils/analyticsLimits'
import {
  useRecipeTatApi,
  type RecipeTatEquipmentRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'
import {
  equipmentSignals,
  isPeerGroupComparable,
  SIGNAL_META
} from '~/utils/equipmentSignals'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { todayStamp } from '~/utils/dateTime'

const props = defineProps<{
  fabs: string[]
  toolType: RecipeTatToolType
  dateRange: { start: string, end: string }
}>()

const { fetchRecipeTatEquipments } = useRecipeTatApi()

const selected = ref<string[]>([])

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined
}))

const cacheKey = computed(
  () => `recipe-tat-equipments:${queryParams.value.toolType}`
    + `:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeTatEquipments(queryParams.value),
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
// 조회하면(= 설계 3.5절의 사무실 확인 절차) 에코가 빈 목록인 채로 데이터는
// 전 fab을 덮기 때문입니다. 선택한 fab 중 한 곳에 측정이 하나도 없어
// 결과적으로 한 fab만 남는 경우도 행을 세는 쪽이 맞습니다.
const peerGroupComparable = computed(() => isPeerGroupComparable(equipmentRows.value))

const selectedRows = computed(
  () => equipmentRows.value.filter(row => selected.value.includes(row.eqp_id))
)

// 내보내기 -------------------------------------------------------------------

// 초·비율은 화면 표기(1h 12m, 62.1%)가 아니라 원시 수치로 냅니다 — 스프레드시트로
// 가는 값은 다시 계산될 것이므로, 사람이 읽기 좋은 포맷은 여기서 손해입니다.
// 열 이름에 단위를 붙여 무엇으로 읽어야 하는지만 못 박습니다.
const fleetTable = (rows: RecipeTatEquipmentRow[]) => ({
  headers: [
    'eqp_id', 'fab', 'model', 'exec_count', 'total_meastime_sec',
    'occupancy_pct', 'avg_meastime_sec', 'recipe_count', 'tat_index', 'signals'
  ],
  // 배지는 화면과 같은 판정을 따릅니다. 또래 집단이 섞였으면 화면에서도
  // 비어 있으므로 CSV도 비웁니다 — 표에 없는 판정을 파일로만 내보내면
  // 그 파일이 화면보다 더 단정적으로 읽힙니다.
  data: rows.map(row => [
    row.eqp_id,
    row.fab_name,
    row.eqp_model_cd,
    row.exec_count,
    row.total_meastime,
    (row.occupancy * 100).toFixed(1),
    Math.round(row.avg_meastime),
    row.recipe_count,
    row.tat_index === null ? '' : row.tat_index.toFixed(2),
    (peerGroupComparable.value ? equipmentSignals(row, percentiles.value) : [])
      .map(signal => SIGNAL_META[signal].label)
      .join(' | ')
  ])
})

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-equipments-${todayStamp()}.csv`
})

const toast = useToast()

const downloadFleetCsv = (rows: RecipeTatEquipmentRow[]) => {
  const { headers, data } = fleetTable(rows)
  downloadCsv(exportFileName.value, headers, data)
}

const copyFleetTable = async (rows: RecipeTatEquipmentRow[]) => {
  const { headers, data } = fleetTable(rows)
  const ok = await copyTableToClipboard(headers, data)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
