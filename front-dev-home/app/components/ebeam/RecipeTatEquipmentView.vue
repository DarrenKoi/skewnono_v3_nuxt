<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="status === 'pending' && !equipmentRows.length"
      title="장비별 데이터를 불러오는 중입니다."
    />
    <!-- 전체 요약과 같은 빈 상태입니다(설계 3.3절) — 문구만 이 뷰의 것입니다. -->
    <AppEmptyState
      v-else-if="!equipmentRows.length"
      title="이 기간에 측정한 장비가 없습니다."
      description="기간을 넓히거나 다른 fab을 선택해보세요."
    />

    <template v-else>
      <EbeamRecipeTatFleetTable
        :rows="equipmentRows"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        @update:selected="selected = $event"
        @download="downloadFleetExcel"
        @copy="copyFleetTable"
      />

      <EbeamRecipeTatEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
        @loaded="comparePayload = $event"
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
  type RecipeTatEquipmentCompareResponse,
  type RecipeTatEquipmentRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'
import { copyTableToClipboard } from '~/utils/csvDownload'
import { buildTatEquipmentWorkbook } from '~/utils/equipmentExport'
import { downloadWorkbook } from '~/utils/xlsx'
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

const selectedRows = computed(
  () => equipmentRows.value.filter(row => selected.value.includes(row.eqp_id))
)

// 비교 패널이 올려보내는 응답. 장비 선택이 비면 패널이 언마운트되므로
// 여기서 직접 비웁니다 — 그러지 않으면 이전 선택의 시트가 파일에 남습니다.
const comparePayload = ref<RecipeTatEquipmentCompareResponse | null>(null)
watch(selected, (value) => {
  if (value.length === 0) comparePayload.value = null
})

// 내보내기 -------------------------------------------------------------------

// 화면·클립보드·파일이 같은 열을 쓰도록 `장비` 시트 하나에서 다 끌어옵니다.
// 열 목록을 두 벌 두면 한쪽만 고쳐지고, 그 어긋남은 파일을 열기 전까지
// 보이지 않습니다.
const equipmentSheet = (rows: RecipeTatEquipmentRow[]) =>
  buildTatEquipmentWorkbook({ equipments: rows, compare: null })[0]!

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-equipments-${todayStamp()}.xlsx`
})

const toast = useToast()

const downloadFleetExcel = async (rows: RecipeTatEquipmentRow[]) => {
  await downloadWorkbook(
    exportFileName.value,
    buildTatEquipmentWorkbook({ equipments: rows, compare: comparePayload.value })
  )
}

const copyFleetTable = async (rows: RecipeTatEquipmentRow[]) => {
  const sheet = equipmentSheet(rows)
  const ok = await copyTableToClipboard(sheet.rows[0] as string[], sheet.rows.slice(1))
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
