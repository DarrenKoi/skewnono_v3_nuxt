<template>
  <div class="px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM 측정 상세"
      :subtitle="filename"
    >
      <template #leading>
        <AppBackButton
          :to="`/afm/${toolId}`"
          label="검색으로"
        />
      </template>
      <template #actions>
        <UDropdownMenu
          :items="exportItems"
          :content="{ align: 'end' }"
          :ui="{ content: 'w-64' }"
        >
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            trailing-icon="i-lucide-chevron-down"
            label="Excel 다운로드"
          />
        </UDropdownMenu>
      </template>
    </EbeamMetaBar>

    <AppLoadingState
      v-if="pending"
      title="측정 상세 정보를 불러오는 중입니다."
    />
    <p
      v-else-if="!payload"
      class="dashboard-surface rounded-(--sk-r-card) px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-400"
    >
      측정 상세 정보를 불러오지 못했습니다.
    </p>
    <div
      v-else
      class="grid gap-6 lg:grid-cols-12"
    >
      <div class="space-y-6 lg:col-span-5 min-[112.5rem]:col-span-4">
        <AfmDetailInfoPanel
          :information="payload.information"
          :summary="payload.summary"
        />
        <AfmDetailMeasurementPointsTable
          v-model:selected-point="selectedPoint"
          :data="payload.data"
          :available-points="payload.available_points"
        />
      </div>
      <div class="grid content-start gap-6 lg:col-span-7 min-[112.5rem]:col-span-8 min-[112.5rem]:grid-cols-8">
        <div class="space-y-6 min-[112.5rem]:col-span-5">
          <AfmDetailSummaryScatterChart
            :summary="payload.summary"
            :export-name="`${filename}-summary-scatter`"
          />
          <UAlert
            v-if="profileError || imageError"
            color="error"
            variant="soft"
            icon="i-lucide-triangle-alert"
            :title="`포인트 ${selectedPoint}의 프로파일을 불러오지 못했습니다.`"
          />
          <div class="grid gap-6 md:grid-cols-2">
            <AfmDetailHeatmapChart
              :profile="profile"
              :loading="profilePending"
              :export-name="`${filename}-heatmap`"
            />
            <AfmDetailHistogramChart
              :profile="profile"
              :loading="profilePending"
              :export-name="`${filename}-histogram`"
            />
          </div>
        </div>
        <div class="space-y-6 min-[112.5rem]:col-span-3">
          <AfmDetailProfileImage
            :url="imageUrl"
            :point="selectedPoint"
            :filename="filename"
            :loading="imagePending"
          />
          <AfmDetailAnalysisImages
            :tool="toolName"
            :filename="filename"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { DropdownMenuItem } from '@nuxt/ui'
import type { ExportTable } from '~/utils/afmExport'

// `key` remounts the page per measurement, so the route params are read once.
definePageMeta({
  layout: 'hub',
  key: route => route.path
})

const route = useRoute()
const toolId = String(route.params.tool ?? '')
const filename = String(route.params.filename ?? '')
const toolName = toolId.toUpperCase()

const { useAfmDetail, fetchProfile, fetchImage } = useAfmDetailApi()

const { data: detailResponse, pending } = useAfmDetail(toolName, filename)

const payload = computed(() => detailResponse.value?.data)
const information = computed(() => payload.value?.information ?? {})
const summaryRows = computed(() => payload.value?.summary ?? [])
const detailRows = computed(() => payload.value?.data ?? [])

const selectedPoint = ref('')

watch(payload, (next) => {
  if (!selectedPoint.value) selectedPoint.value = next?.available_points?.[0] ?? ''
}, { immediate: true })

// Per-point data: refetched when the point changes, and the latest request wins.
// A 404 means the point has no such file, which is an answer rather than a failure.
function usePointData<T>(kind: string, load: (point: string) => Promise<T>, empty: T) {
  return useAsyncData(
    `afm-${kind}:${toolName}:${filename}`,
    async () => {
      if (!selectedPoint.value) return empty
      try {
        return await load(selectedPoint.value)
      } catch (err) {
        if ((err as { statusCode?: number }).statusCode === 404) return empty
        throw err
      }
    },
    { watch: [selectedPoint], default: () => empty }
  )
}

const { data: profile, pending: profilePending, error: profileError } = usePointData(
  'profile',
  async point => (await fetchProfile(toolName, filename, point)).data ?? [],
  [] as AfmProfilePoint[]
)
const { data: imageUrl, pending: imagePending, error: imageError } = usePointData(
  'image',
  async point => (await fetchImage(toolName, filename, point)).data?.url ?? null,
  null as string | null
)

const infoCount = computed(() => Object.keys(information.value).length)
const siteCount = computed(() => new Set(summaryRows.value.map(r => r.Site)).size)

const toast = useToast()
const downloadTable = useTableDownload()

const downloadSection = (suffix: string, table: ExportTable) =>
  downloadTable(`${filename}-${suffix}.xlsx`, table.headers, table.rows)

// 섹션 넷을 시트 넷으로. CSV 시절에는 한 파일에 붙여 쌓았습니다.
// 여러 장짜리라 useTableDownload 를 못 타므로 실패 처리는 여기서 하되,
// 문구는 같은 상수를 씁니다.
const downloadCombined = async () => {
  try {
    await downloadWorkbook(`${filename}-all.xlsx`, buildCombinedSheets([
      { label: '측정 정보', table: buildInfoTable(information.value) },
      { label: '사이트별 요약', table: buildSummaryTable(summaryRows.value) },
      { label: '측정 포인트', table: buildDetailedTable(detailRows.value) },
      { label: `프로파일 (포인트 ${selectedPoint.value || '없음'})`, table: buildProfileTable(profile.value) }
    ]))
  } catch {
    toast.add({ ...EXCEL_DOWNLOAD_FAILED })
  }
}

// While a newly picked point is loading, `profile` still holds the previous
// point's rows, so the two exports that carry it wait for the request.
const exportItems = computed<DropdownMenuItem[][]>(() => [
  [{
    label: '전체 (Excel)',
    icon: 'i-lucide-download',
    disabled: profilePending.value
      || (!infoCount.value && !summaryRows.value.length && !detailRows.value.length && !profile.value.length),
    onSelect: () => downloadCombined()
  }],
  [
    {
      label: `측정 정보 (${infoCount.value})`,
      icon: 'i-lucide-info',
      disabled: infoCount.value === 0,
      onSelect: () => downloadSection('info', buildInfoTable(information.value))
    },
    {
      label: `사이트별 요약 (${siteCount.value}개 사이트)`,
      icon: 'i-lucide-table',
      disabled: summaryRows.value.length === 0,
      onSelect: () => downloadSection('summary', buildSummaryTable(summaryRows.value))
    },
    {
      label: `측정 포인트 (${detailRows.value.length})`,
      icon: 'i-lucide-list',
      disabled: detailRows.value.length === 0,
      onSelect: () => downloadSection('detailed', buildDetailedTable(detailRows.value))
    },
    {
      label: `프로파일 — 포인트 ${selectedPoint.value || '없음'} (${profile.value.length})`,
      icon: 'i-lucide-line-chart',
      disabled: profilePending.value || profile.value.length === 0,
      onSelect: () => downloadSection(`profile-point${safeFilePart(selectedPoint.value)}`, buildProfileTable(profile.value))
    }
  ]
])
</script>
