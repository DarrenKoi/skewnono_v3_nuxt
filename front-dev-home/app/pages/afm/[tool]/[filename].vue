<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-5 md:p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="flex min-w-0 items-start gap-3">
          <AppBackButton
            :to="`/afm/${toolId}`"
            label="Back to search"
            class="mt-0.5 shrink-0"
          />
          <div class="min-w-0">
            <AfmBreadcrumb
              :tool="toolId"
              :current="filename"
              class="mb-2"
            />
            <h1 class="truncate text-xl md:text-2xl font-semibold tracking-tight font-mono">
              {{ filename }}
            </h1>
            <p class="sk-meta mt-1">
              {{ toolId.toUpperCase() }}
              <span v-if="information?.['Recipe ID']"> · {{ information['Recipe ID'] }}</span>
              <span v-if="information?.['Lot ID']"> · {{ information['Lot ID'] }}</span>
            </p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
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
            >
              내보내기
            </UButton>
          </UDropdownMenu>
        </div>
      </div>
    </section>

    <AppLoadingState
      v-if="pending"
      variant="inline"
      class="dashboard-surface rounded-2xl"
      title="측정 상세 정보를 불러오는 중입니다."
    />
    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      Failed to load measurement detail.
    </div>
    <template v-else-if="payload">
      <div class="grid gap-5 lg:grid-cols-12">
        <div class="space-y-5 lg:col-span-5">
          <AfmDetailInfoPanel
            :information="information"
            :summary="payload.summary"
          />
          <AfmDetailMeasurementPointsTable
            :data="payload.data"
            :available-points="payload.available_points"
            :selected-point="selectedPoint"
            @update:selected-point="selectedPoint = $event"
          />
        </div>
        <div class="space-y-5 lg:col-span-7">
          <AfmDetailSummaryScatterChart
            :summary="payload.summary"
            :export-name="`${filename}-summary-scatter`"
          />
          <div class="grid gap-5 md:grid-cols-2">
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
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'
import type { DropdownMenuItem } from '@nuxt/ui'
import type { ExportTable } from '~/utils/afmExport'

definePageMeta({
  layout: 'hub',
  key: route => route.path
})

const route = useRoute()
const toolId = computed(() => String(route.params.tool ?? ''))
const filename = computed(() => String(route.params.filename ?? ''))
const toolName = computed(() => toolId.value.toUpperCase())

const { useAfmDetail, fetchProfile, fetchImage } = useAfmDetailApi()

const { data: detailResponse, pending, error } = await useAfmDetail(toolName.value, filename.value)

const payload = computed(() => detailResponse.value?.data)
const information = computed(() => payload.value?.information ?? {})

const selectedPoint = ref<string>('')

watch(payload, (next) => {
  if (next?.available_points?.length && !selectedPoint.value) {
    selectedPoint.value = next.available_points[0] ?? ''
  }
}, { immediate: true })

const useTokenedLoader = <T, R>(
  fetcher: (point: string) => Promise<T>,
  extract: (res: T) => R,
  empty: R
) => {
  const data = ref(empty) as Ref<R>
  const pending = ref(false)
  let token = 0

  const run = async (point: string) => {
    const t = ++token
    data.value = empty
    if (!point) {
      pending.value = false
      return
    }
    pending.value = true
    try {
      const res = await fetcher(point)
      if (t === token) data.value = extract(res)
    } catch {
      if (t === token) data.value = empty
    } finally {
      if (t === token) pending.value = false
    }
  }

  return { data, pending, run }
}

const profileLoader = useTokenedLoader(
  (point: string) => fetchProfile(toolName.value, filename.value, point),
  res => res.data ?? [],
  [] as AfmProfilePoint[]
)
const imageLoader = useTokenedLoader(
  (point: string) => fetchImage(toolName.value, filename.value, point),
  res => res.data?.url ?? null,
  null as string | null
)

const profile = profileLoader.data
const profilePending = profileLoader.pending
const imageUrl = imageLoader.data
const imagePending = imageLoader.pending

const summaryRows = computed(() => payload.value?.summary ?? [])
const detailRows = computed(() => payload.value?.data ?? [])
const infoEntries = computed(() => Object.entries(information.value))
const siteCount = computed(() => new Set(summaryRows.value.map(r => r.Site)).size)

const safePoint = () => selectedPoint.value.replace(/[^a-zA-Z0-9]+/g, '_') || 'point'

const toast = useToast()
const downloadTable = useTableDownload()

const downloadSection = (suffix: string, table: ExportTable) =>
  downloadTable(`${filename.value}-${suffix}.xlsx`, table.headers, table.rows)

const downloadInfo = () => downloadSection('info', buildInfoTable(information.value))
const downloadSummary = () => downloadSection('summary', buildSummaryTable(summaryRows.value))
const downloadDetailed = () => downloadSection('detailed', buildDetailedTable(detailRows.value))
const downloadProfile = () =>
  downloadSection(`profile-point${safePoint()}`, buildProfileTable(profile.value))

// 섹션 넷을 시트 넷으로. CSV 시절에는 한 파일에 붙여 쌓았습니다.
// 여러 장짜리라 useTableDownload 를 못 타므로 실패 처리는 여기서 하되,
// 문구는 같은 상수를 씁니다.
const downloadCombined = async () => {
  try {
    await downloadWorkbook(`${filename.value}-all.xlsx`, buildCombinedSheets([
      { label: 'Measurement Info', table: buildInfoTable(information.value) },
      { label: 'Summary (by site)', table: buildSummaryTable(summaryRows.value) },
      { label: 'Detailed Points', table: buildDetailedTable(detailRows.value) },
      { label: `Profile (point ${selectedPoint.value || 'none'})`, table: buildProfileTable(profile.value) }
    ]))
  } catch {
    toast.add({ ...EXCEL_DOWNLOAD_FAILED })
  }
}

const hasAnyData = computed(() =>
  infoEntries.value.length > 0
  || summaryRows.value.length > 0
  || detailRows.value.length > 0
  || profile.value.length > 0
)

const exportItems = computed<DropdownMenuItem[][]>(() => [
  [{
    label: 'Download All (Excel)',
    icon: 'i-lucide-download',
    disabled: !hasAnyData.value,
    onSelect: () => downloadCombined()
  }],
  [
    {
      label: `Measurement Info (${infoEntries.value.length})`,
      icon: 'i-lucide-info',
      disabled: infoEntries.value.length === 0,
      onSelect: () => downloadInfo()
    },
    {
      label: `Summary (${siteCount.value} sites)`,
      icon: 'i-lucide-table',
      disabled: summaryRows.value.length === 0,
      onSelect: () => downloadSummary()
    },
    {
      label: `Detailed Points (${detailRows.value.length})`,
      icon: 'i-lucide-list',
      disabled: detailRows.value.length === 0,
      onSelect: () => downloadDetailed()
    },
    {
      label: `Profile — point ${selectedPoint.value || '—'} (${profile.value.length})`,
      icon: 'i-lucide-line-chart',
      disabled: profile.value.length === 0,
      onSelect: () => downloadProfile()
    }
  ]
])

watch(selectedPoint, (point) => {
  profileLoader.run(point)
  imageLoader.run(point)
}, { immediate: true })
</script>
