<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fabs.join(' + ')}`"
      title="Recipe 현황"
      :as-of="bounds.max ?? undefined"
    >
      <template #toggle>
        <div class="flex flex-wrap items-center gap-2.5">
          <div
            role="tablist"
            aria-label="Recipe 현황 탭"
            class="inline-flex items-center gap-1"
          >
            <SkNavPill
              v-for="tab in TABS"
              :key="tab.value"
              :label="tab.label"
              :icon="tab.icon"
              :active="activeTab === tab.value"
              @click="selectTab(tab.value)"
            />
          </div>
          <EbeamDateRangePopover
            v-model="dateRange"
            :anchor-date="bounds.max ?? undefined"
            :min-date="bounds.min ?? undefined"
            :presets="DATE_PRESETS"
            trigger-class="h-9 px-3.5 text-sm"
          />
        </div>
      </template>
    </EbeamMetaBar>

    <AppEmptyState
      v-if="error"
      icon="i-lucide-triangle-alert"
      title="Recipe 현황 데이터를 불러오지 못했습니다."
      description="잠시 후 다시 시도해 주세요."
    />
    <AppLoadingState
      v-else-if="!data"
      title="Recipe 현황 데이터를 불러오는 중입니다."
    />
    <AppEmptyState
      v-else-if="!data.anchor_date && !data.equipments.length"
      title="적재된 작업 이력이 없습니다."
      description="선택한 fab의 장비에 MES 작업 이력이 아직 없습니다."
    />

    <template v-else>
      <div class="dashboard-surface flex flex-wrap divide-x divide-(--sk-border) rounded-[var(--sk-r-card)] py-2.5">
        <div
          v-for="kpi in kpis"
          :key="kpi.label"
          class="flex min-w-[9rem] flex-1 flex-col px-4"
        >
          <span
            class="text-2xl font-semibold leading-tight tabular-nums"
            :class="kpi.bad ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
          >{{ kpi.value }}</span>
          <span class="mt-0.5 sk-meta font-semibold">
            {{ kpi.label }}
            <span
              v-if="kpi.sub"
              class="font-normal tabular-nums"
            >· {{ kpi.sub }}</span>
          </span>
        </div>
      </div>

      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-trending-up"
              class="h-4 w-4 text-(--sk-ink-muted)"
            />
            <h3 class="sk-title">
              일별 추이
            </h3>
            <span class="sk-meta tabular-nums">{{ data.start_date }} ~ {{ data.end_date }}</span>
          </div>
        </template>
        <EbeamRecipeUsageDailyChart
          :points="data.daily"
          export-name="recipe-usage-daily-trend"
          class="h-[280px]"
        />
      </UCard>

      <!-- @vue-generic {RecipeUsageRankingRow} -->
      <EbeamFailIssueRankingTable
        v-if="activeTab === 'tat'"
        title="Recipe별 측정 시간"
        search-placeholder="recipe_id / eqp_id 검색…"
        download-label="Excel 다운로드"
        :rows="data.recipes"
        :columns="tatColumns"
        :sortable-ids="['runs', 'wafers', 'meas_min', 'avg_meas_min']"
        default-sort-id="meas_min"
        :reset-key="cacheKey"
        :search-predicate="recipeSearchPredicate"
        @download="rows => exportTable('tat', rows.map(recipeExport), 'download')"
        @copy="rows => exportTable('tat', rows.map(recipeExport), 'copy')"
      >
        <template #recipe_id-cell="{ row }">
          <EbeamRecipeUsageRecipeLink :recipe-id="row.original.recipe_id" />
        </template>
      </EbeamFailIssueRankingTable>

      <template v-else-if="activeTab === 'fail'">
        <AppEmptyState
          v-if="!failRows.length"
          title="이 기간에 fail로 집계된 작업이 없습니다."
        />
        <!-- @vue-generic {RecipeUsageFailRow} -->
        <EbeamFailIssueRankingTable
          v-else
          title="Recipe별 Fail"
          search-placeholder="recipe_id / eqp_id 검색…"
          download-label="Excel 다운로드"
          :rows="failRows"
          :columns="failColumns"
          :sortable-ids="['fail_runs', 'runs', 'fail_rate_ranked']"
          :pin-last="{ fail_rate_ranked: row => row.low_sample }"
          default-sort-id="fail_runs"
          :reset-key="cacheKey"
          :search-predicate="recipeSearchPredicate"
          @download="rows => exportTable('fail', rows.map(recipeExport), 'download')"
          @copy="rows => exportTable('fail', rows.map(recipeExport), 'copy')"
        >
          <template #title-extra>
            <span class="sk-meta">작업 {{ RECIPE_USAGE_MIN_FAIL_RUNS }}회 미만인 recipe는 Fail 비율 순위에서 제외합니다.</span>
          </template>
          <template #recipe_id-cell="{ row }">
            <EbeamRecipeUsageRecipeLink :recipe-id="row.original.recipe_id" />
          </template>
          <template #fail_rate_ranked-cell="{ row }">
            {{ formatRate(row.original.fail_rate, 1) }}
            <span
              v-if="row.original.low_sample"
              class="ml-1 sk-meta"
            >표본 부족</span>
          </template>
        </EbeamFailIssueRankingTable>
      </template>

      <!-- @vue-generic {RecipeUsageEquipmentRow} -->
      <EbeamFailIssueRankingTable
        v-else
        title="장비별 현황"
        search-placeholder="eqp_id / model / recipe 검색…"
        download-label="Excel 다운로드"
        :rows="data.equipments"
        :columns="equipmentColumns"
        :sortable-ids="['runs', 'wafers', 'meas_min', 'avg_meas_min', 'fail_runs', 'fail_rate', 'recipe_count']"
        default-sort-id="meas_min"
        :reset-key="cacheKey"
        :search-predicate="equipmentSearchPredicate"
        :meta="EQUIPMENT_TABLE_META"
        @download="rows => exportTable('equipment', rows.map(equipmentExport), 'download')"
        @copy="rows => exportTable('equipment', rows.map(equipmentExport), 'copy')"
      >
        <template #title-extra>
          <span
            v-if="idleToolCount"
            class="sk-meta"
          >이 기간에 작업이 없는 장비 {{ idleToolCount.toLocaleString() }}대는 흐리게 표시합니다.</span>
        </template>
        <template #top_recipe-cell="{ row }">
          <EbeamRecipeUsageRecipeLink
            v-if="row.original.top_recipe"
            :recipe-id="row.original.top_recipe"
          />
          <template v-else>
            —
          </template>
        </template>
      </EbeamFailIssueRankingTable>

      <ul class="list-disc space-y-0.5 rounded-(--sk-r-chip) bg-(--sk-muted-surface) py-2.5 pl-8 pr-4 sk-meta leading-relaxed">
        <li>Fail은 정상 종료되지 않았거나 MES가 최종 데이터로 채택하지 않은 작업 수입니다. 사유는 저장되지 않습니다.</li>
        <li>평균 측정 시간은 측정 시간 합을 작업 수로 나눈 값입니다. 종료되지 않은 작업은 0분으로 집계되므로 fail이 많으면 실제보다 낮게 보입니다.</li>
        <li>데이터는 전날까지 반영됩니다. 오늘 작업은 포함되지 않습니다.</li>
        <li>Fab은 장비의 현재 소속(fab_name) 기준입니다. 장비가 과거 다른 fab에 있을 때의 실적은 제외됩니다.</li>
      </ul>
    </template>

    <EbeamRecipeUsageDetail
      :fabs="fabs"
      :tool-label="toolLabel"
      :tool-type="toolType"
    />
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { TableMeta } from '@tanstack/vue-table'
import { formatRate } from '~/composables/useFailIssueApi'
import { formatSecondsAsDuration } from '~/composables/useRecipeTatApi'
import type {
  RecipeUsageEquipmentRow,
  RecipeUsageRankingRow,
  RecipeUsageToolType
} from '~/composables/useRecipeUsageApi'
import { todayStamp } from '~/utils/dateTime'
import { matchFeatureFromPath } from '~/utils/features'
import {
  RECIPE_USAGE_MIN_FAIL_RUNS,
  clampDateRange,
  matchesRecipeTokens,
  rankRecipeFails,
  type RecipeUsageFailRow
} from '~/utils/recipeUsage'
import { copyTableToClipboard } from '~/utils/tableExport'

const props = defineProps<{
  fabs: string[]
  toolLabel: string
  toolType: RecipeUsageToolType
}>()

const TABS = [
  { value: 'tat', label: 'Recipe TAT', icon: 'i-lucide-timer' },
  { value: 'fail', label: 'Fail', icon: 'i-lucide-circle-alert' },
  { value: 'equipment', label: '장비별', icon: 'i-lucide-microscope' }
] as const
type StatusTab = typeof TABS[number]['value']

const isTab = (value: unknown): value is StatusTab => TABS.some(tab => tab.value === value)

// The window ends at the anchor date, which is yesterday at best, so a
// "Today" preset would name a day that has no data. The popover subtracts
// `days` from the end and the API range is inclusive, hence the -1.
const DATE_PRESETS = [7, 14, 30, 60, 90].map(days => ({ label: `Last ${days} days`, days: days - 1 }))

const route = useRoute()
const router = useRouter()

// The URL owns the active tab, as in EbeamRecipeStatusView. A tab carried over
// from the Hitachi page (?tab=align) is not one of ours and falls back.
const lastTab = useState<StatusTab>('recipe-usage-status-tab', () => 'tat')

const queryTab = computed(() => {
  const raw = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab
  return isTab(raw) ? raw : null
})
const activeTab = computed<StatusTab>(() => queryTab.value ?? lastTab.value)

watch(activeTab, (tab) => {
  lastTab.value = tab
}, { immediate: true })

// Path guard: never rewrite the query of a route we are navigating away to.
watch(() => [route.path, route.query.tab] as const, ([path]) => {
  if (matchFeatureFromPath(path) !== 'recipe-status') return
  if (queryTab.value !== activeTab.value) {
    router.replace({ query: { ...route.query, tab: activeTab.value } })
  }
}, { immediate: true })

const selectTab = (tab: StatusTab) => {
  router.replace({ query: { ...route.query, tab } })
}

const { fetchRecipeUsageStatus } = useRecipeUsageApi()
const downloadTable = useTableDownload()
const toast = useToast()

// Empty until the user picks a range: the server resolves the default window.
const userDateRange = ref({ start: '', end: '' })

const cacheKey = computed(
  () => `recipe-usage-status:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${userDateRange.value.start || 'auto'}:${userDateRange.value.end || 'auto'}`
)

const { data, error } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeUsageStatus(props.toolType, props.fabs, userDateRange.value),
  { watch: [cacheKey] }
)

// The loaded window's edges. Held apart from `data` so the date picker keeps
// its limits while the next range is still loading.
const bounds = ref<{ min: string | null, max: string | null }>({ min: null, max: null })
watch(data, (next) => {
  if (next) bounds.value = { min: next.data_start, max: next.anchor_date }
}, { immediate: true })

const dateRange = computed({
  get: () => userDateRange.value.start && userDateRange.value.end
    ? userDateRange.value
    : { start: data.value?.start_date ?? '', end: data.value?.end_date ?? '' },
  set: (next) => {
    userDateRange.value = clampDateRange(next, bounds.value.min, bounds.value.max)
  }
})

const minutes = (value: number) => formatSecondsAsDuration(value * 60)

const kpis = computed(() => {
  const summary = data.value?.summary
  if (!summary) return []
  return [
    { label: '작업 수', value: summary.runs.toLocaleString() },
    { label: 'Wafer', value: summary.wafers.toLocaleString() },
    { label: '총 측정 시간', value: minutes(summary.meas_min) },
    { label: '평균 측정 시간', value: minutes(summary.avg_meas_min), sub: '작업당' },
    {
      label: 'Fail',
      value: summary.fail_runs.toLocaleString(),
      sub: formatRate(summary.fail_rate, 1),
      bad: summary.fail_runs > 0
    },
    { label: 'Recipe', value: summary.recipe_count.toLocaleString() },
    {
      label: '가동 장비',
      value: summary.active_tool_count.toLocaleString(),
      sub: `전체 ${summary.tool_count.toLocaleString()}대`
    }
  ]
})

const failRows = computed(() => rankRecipeFails(data.value?.recipes ?? []))
const idleToolCount = computed(() => (data.value?.equipments ?? []).filter(row => row.runs === 0).length)

const recipeSearchPredicate = (row: RecipeUsageRankingRow, term: string) =>
  matchesRecipeTokens(`${row.recipe_id} ${row.eqp_ids.join(' ')}`, term)

const equipmentSearchPredicate = (row: RecipeUsageEquipmentRow, term: string) =>
  `${row.eqp_id} ${row.eqp_model_cd} ${row.top_recipe ?? ''}`.toLowerCase().includes(term)

// A roster tool with no run in the window stays in the table, dimmed: its
// absence from the work is the information.
const EQUIPMENT_TABLE_META: TableMeta<RecipeUsageEquipmentRow> = {
  class: { tr: row => row.original.runs === 0 ? 'opacity-50' : '' }
}

const toolsCell = (eqpIds: string[]) =>
  eqpIds.length > 3 ? `${eqpIds.slice(0, 3).join(', ')} 외 ${eqpIds.length - 3}대` : eqpIds.join(', ')

const multiFab = computed(() => props.fabs.length > 1)

const recipeTailColumns = computed<TableColumn<RecipeUsageRankingRow>[]>(() => [
  { id: 'eqp_ids', header: '장비', cell: ({ row }) => toolsCell(row.original.eqp_ids) },
  ...(multiFab.value
    ? [{ id: 'fab_names', header: 'Fab', cell: ({ row }) => row.original.fab_names.join(', ') } satisfies TableColumn<RecipeUsageRankingRow>]
    : []),
  { accessorKey: 'last_start', header: '최근 시작' }
])

const tatColumns = computed<TableColumn<RecipeUsageRankingRow>[]>(() => [
  { accessorKey: 'recipe_id', header: 'recipe_id' },
  { accessorKey: 'runs', header: '작업 수', cell: ({ row }) => row.original.runs.toLocaleString() },
  { accessorKey: 'wafers', header: 'Wafer', cell: ({ row }) => row.original.wafers.toLocaleString() },
  { accessorKey: 'meas_min', header: '총 측정 시간', cell: ({ row }) => minutes(row.original.meas_min) },
  { accessorKey: 'avg_meas_min', header: '평균 측정 시간', cell: ({ row }) => minutes(row.original.avg_meas_min) },
  ...recipeTailColumns.value
])

const failColumns = computed<TableColumn<RecipeUsageFailRow>[]>(() => [
  { accessorKey: 'recipe_id', header: 'recipe_id' },
  { accessorKey: 'fail_runs', header: 'Fail', cell: ({ row }) => row.original.fail_runs.toLocaleString() },
  { accessorKey: 'runs', header: '작업 수', cell: ({ row }) => row.original.runs.toLocaleString() },
  { accessorKey: 'fail_rate_ranked', header: 'Fail 비율' },
  ...(recipeTailColumns.value as TableColumn<RecipeUsageFailRow>[])
])

const equipmentColumns = computed<TableColumn<RecipeUsageEquipmentRow>[]>(() => [
  { accessorKey: 'eqp_id', header: 'eqp_id' },
  ...(multiFab.value ? [{ accessorKey: 'fab_name', header: 'Fab' }] : []),
  { accessorKey: 'eqp_model_cd', header: 'Model' },
  { accessorKey: 'runs', header: '작업 수', cell: ({ row }) => row.original.runs.toLocaleString() },
  { accessorKey: 'wafers', header: 'Wafer', cell: ({ row }) => row.original.wafers.toLocaleString() },
  { accessorKey: 'meas_min', header: '총 측정 시간', cell: ({ row }) => minutes(row.original.meas_min) },
  { accessorKey: 'avg_meas_min', header: '평균 측정 시간', cell: ({ row }) => minutes(row.original.avg_meas_min) },
  { accessorKey: 'fail_runs', header: 'Fail', cell: ({ row }) => row.original.fail_runs.toLocaleString() },
  { accessorKey: 'fail_rate', header: 'Fail 비율', cell: ({ row }) => formatRate(row.original.fail_rate, 1) },
  { accessorKey: 'recipe_count', header: 'Recipe 수', cell: ({ row }) => row.original.recipe_count.toLocaleString() },
  { accessorKey: 'top_recipe', header: '최다 recipe' },
  { accessorKey: 'last_start', header: '최근 시작', cell: ({ row }) => row.original.last_start ?? '작업 없음' }
])

// What each tab exports: raw fields, minutes left as numbers for the sheet.
const recipeExport = (row: RecipeUsageRankingRow) => ({
  recipe_id: row.recipe_id,
  runs: row.runs,
  wafers: row.wafers,
  meas_min: row.meas_min,
  avg_meas_min: row.avg_meas_min,
  fail_runs: row.fail_runs,
  fail_rate: row.fail_rate,
  eqp_ids: row.eqp_ids.join(', '),
  fab_names: row.fab_names.join(', '),
  last_start: row.last_start
})

const equipmentExport = (row: RecipeUsageEquipmentRow) =>
  ({ ...row, top_recipe: row.top_recipe ?? '', last_start: row.last_start ?? '' })

const exportTable = async (
  tab: StatusTab,
  records: Record<string, unknown>[],
  action: 'download' | 'copy'
) => {
  const headers = Object.keys(records[0] ?? {})
  const cells = records.map(record => headers.map(header => record[header]))
  if (action === 'download') {
    const fab = (props.fabs.join('+') || 'all').toLowerCase()
    await downloadTable(`${props.toolType}-${fab}-recipe-${tab}-${todayStamp()}.xlsx`, headers, cells)
    return
  }
  const ok = await copyTableToClipboard(headers, cells)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
