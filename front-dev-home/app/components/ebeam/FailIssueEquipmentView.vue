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
        @download="downloadFleetCsv"
        @copy="copyFleetTable"
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
import {
  FAIL_SIGNAL_META,
  failEquipmentSignals
} from '~/utils/failEquipmentSignals'
import {
  useFailIssueApi,
  type FailIssueEquipmentRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { todayStamp } from '~/utils/dateTime'

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

// 내보내기 -------------------------------------------------------------------

// 표와 같은 축(align/meas)만 냅니다. 응답은 두 축을 다 담고 있지만, 보고 있는
// 탭과 다른 열이 섞여 나오면 파일만 보고는 어느 축인지 알 수 없습니다.
// 대신 파일명과 열 이름에 축을 박습니다.
const fleetTable = (rows: FailIssueEquipmentRow[]) => {
  const isAlign = props.section === 'align'
  const prefix = isAlign ? 'align' : 'meas'
  return {
    headers: [
      'eqp_id', 'fab', 'model', 'exec_count',
      `${prefix}_fail_count`, `${prefix}_fail_rate_pct`, `${prefix}_expected`,
      `${prefix}_index`, `${prefix}_index_low`, `${prefix}_index_high`,
      'recipe_count', 'signals'
    ],
    // 배지는 화면과 같은 판정을 따릅니다. 또래 집단이 섞였으면 화면에서도
    // 비어 있으므로 CSV도 비웁니다 — 표에 없는 판정을 파일로만 내보내면
    // 그 파일이 화면보다 더 단정적으로 읽힙니다.
    data: rows.map((row) => {
      const signalInput = {
        index: isAlign ? row.align_index : row.meas_index,
        index_low: isAlign ? row.align_index_low : row.meas_index_low,
        index_high: isAlign ? row.align_index_high : row.meas_index_high,
        recipe_count: row.recipe_count,
        top_recipe_share: row.top_recipe_share
      }
      return [
        row.eqp_id,
        row.fab_name,
        row.eqp_model_cd,
        row.exec_count,
        isAlign ? row.align_fail_count : row.meas_fail_count,
        ((isAlign ? row.align_fail_rate : row.meas_fail_rate) * 100).toFixed(2),
        (isAlign ? row.align_expected : row.meas_expected).toFixed(1),
        signalInput.index === null ? '' : signalInput.index.toFixed(2),
        signalInput.index_low === null ? '' : signalInput.index_low.toFixed(2),
        signalInput.index_high === null ? '' : signalInput.index_high.toFixed(2),
        row.recipe_count,
        (peerGroupComparable.value
          ? failEquipmentSignals(signalInput, percentiles.value)
          : []
        ).map(signal => FAIL_SIGNAL_META[signal].label).join(' | ')
      ]
    })
  }
}

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-fail-issue-equipments`
    + `-${props.section}-${todayStamp()}.csv`
})

const toast = useToast()

const downloadFleetCsv = (rows: FailIssueEquipmentRow[]) => {
  const { headers, data } = fleetTable(rows)
  downloadCsv(exportFileName.value, headers, data)
}

const copyFleetTable = async (rows: FailIssueEquipmentRow[]) => {
  const { headers, data } = fleetTable(rows)
  const ok = await copyTableToClipboard(headers, data)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
