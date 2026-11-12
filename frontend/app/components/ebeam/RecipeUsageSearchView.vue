<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fabs.join(' + ')}`"
      title="Recipe 검색"
      subtitle="MES 작업 이력과 장비에 있는 recipe를 recipe_id로 찾습니다."
      :stats="[{ key: 'total', value: catalogRows.length.toLocaleString(), label: '전체 recipe' }]"
    />

    <AppEmptyState
      v-if="error"
      icon="i-lucide-triangle-alert"
      title="Recipe 목록을 불러오지 못했습니다."
      description="잠시 후 다시 시도해 주세요."
    />

    <div
      v-else
      class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3"
    >
      <div class="mb-3 flex flex-wrap items-center gap-3">
        <UInput
          v-model="query"
          type="search"
          size="lg"
          icon="i-lucide-search"
          class="min-w-[22rem] flex-1"
          placeholder="recipe_id 검색 — 공백으로 나눈 단어를 모두 포함하는 recipe를 찾습니다"
          aria-label="recipe_id 검색"
        />
        <div
          class="flex items-center gap-1.5"
          role="group"
          aria-label="출처 필터"
        >
          <SkChip
            v-for="option in sourceOptions"
            :key="option.value"
            size="sm"
            :label="option.label"
            :count="option.count.toLocaleString()"
            :active="sourceFilter === option.value"
            @click="sourceFilter = option.value"
          />
          <SkInfoTip
            label="출처"
            :text="RECIPE_USAGE_SOURCE_HELP"
          />
        </div>
        <span class="sk-count-chip">
          {{ sortedRows.length.toLocaleString() }} / {{ catalogRows.length.toLocaleString() }}
        </span>
        <USelect
          v-model="pageSize"
          class="w-[6.5rem]"
          size="xs"
          :items="PAGE_SIZE_OPTIONS"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          label="Excel 다운로드"
          :disabled="sortedRows.length === 0"
          @click="downloadCatalog"
        />
      </div>

      <UTable
        v-model:sorting="sorting"
        :columns="columns"
        :data="pagedRows"
        :sorting-options="MANUAL_SORTING_OPTIONS"
        sticky="header"
        :ui="tableUi"
        @select="(_event: Event, row: TableRow<RecipeUsageCatalogRow>) => selectRecipe(row.original.recipe_id)"
      >
        <template
          v-for="id in SORTABLE_IDS"
          :key="id"
          #[`${id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ column.columnDef.header }}
          </UButton>
        </template>

        <template #recipe_id-cell="{ row }">
          <span class="font-mono font-semibold">{{ row.original.recipe_id }}</span>
        </template>

        <template #tool_count-cell="{ row }">
          <span :title="row.original.eqp_ids.join(', ')">{{ row.original.eqp_ids.length.toLocaleString() }}</span>
        </template>

        <template #source-cell="{ row }">
          <span class="inline-flex h-5 items-center rounded-(--sk-r-sidebar) border border-(--sk-border-soft) bg-(--sk-muted-surface) px-1.5 text-xs font-semibold text-(--sk-ink-muted)">
            {{ RECIPE_USAGE_SOURCE_LABELS[row.original.source] }}
          </span>
        </template>

        <template #empty>
          <div class="py-8 text-center sk-meta">
            조건에 맞는 recipe가 없습니다.
          </div>
        </template>
      </UTable>

      <div class="mt-2 flex items-center justify-between sk-meta">
        <span class="tabular-nums">
          Page {{ page }} / {{ pageCount }}
          <span class="ml-2">
            {{ pageStart.toLocaleString() }}–{{ pageEnd.toLocaleString() }} of {{ sortedRows.length.toLocaleString() }}
          </span>
        </span>
        <div class="flex gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            aria-label="이전 페이지"
            :disabled="page <= 1"
            @click="page -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-right"
            aria-label="다음 페이지"
            :disabled="page >= pageCount"
            @click="page += 1"
          />
        </div>
      </div>

      <ul class="mt-3 list-disc space-y-0.5 border-t border-(--sk-border-soft) pl-5 pt-2.5 sk-meta leading-relaxed">
        <li>행을 선택하면 장비별 사용 이력과 일별 추이를 볼 수 있습니다.</li>
        <li>누적 사용은 전체 기간의 MES 작업 시작 횟수입니다. 장비에만 있는 recipe는 사용 일시가 없습니다.</li>
        <li>Fab은 장비의 현재 소속(fab_name) 기준입니다. 장비가 과거 다른 fab에 있을 때의 실적은 제외됩니다.</li>
      </ul>
    </div>

    <EbeamRecipeUsageDetail
      :fabs="fabs"
      :tool-label="toolLabel"
      :tool-type="toolType"
    />
  </div>
</template>

<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { RecipeUsageCatalogRow, RecipeUsageToolType } from '~/composables/useRecipeUsageApi'
import { todayStamp } from '~/utils/dateTime'
import {
  RECIPE_USAGE_SOURCE_HELP,
  RECIPE_USAGE_SOURCE_LABELS,
  filterRecipeCatalog,
  sortRecipeCatalog,
  type RecipeCatalogSortKey,
  type RecipeUsageSourceFilter
} from '~/utils/recipeUsage'
import { MANUAL_SORTING_OPTIONS, getSortIcon } from '~/utils/tableSorting'

const props = defineProps<{
  fabs: string[]
  toolLabel: string
  toolType: RecipeUsageToolType
}>()

const { fetchRecipeUsageCatalog } = useRecipeUsageApi()
const { selectRecipe } = useRecipeUsageSelection()
const downloadTable = useTableDownload()

const cacheKey = computed(() => `recipe-usage-catalog:${props.toolType}:${props.fabs.join(',') || 'ALL'}`)

const { data, error } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeUsageCatalog(props.toolType, props.fabs),
  { watch: [cacheKey] }
)

const catalogRows = computed(() => data.value?.rows ?? [])

const query = ref('')
const sourceFilter = ref<RecipeUsageSourceFilter>('all')

const textMatched = computed(() => filterRecipeCatalog(catalogRows.value, query.value))

// Counts follow the text search, so a chip says how many rows it would leave.
const sourceOptions = computed(() => [
  { value: 'all' as const, label: '전체', count: textMatched.value.length },
  ...(['both', 'mes', 'tool'] as const).map(source => ({
    value: source,
    label: RECIPE_USAGE_SOURCE_LABELS[source],
    count: textMatched.value.filter(row => row.source === source).length
  }))
])

const SORTABLE_IDS: readonly RecipeCatalogSortKey[] = ['recipe_id', 'tool_count', 'n_uses', 'first_used', 'last_used']
const sorting = ref<SortingState>([{ id: 'last_used', desc: true }])

const sortedRows = computed(() => {
  const current = sorting.value[0]
  const matched = filterRecipeCatalog(textMatched.value, '', sourceFilter.value)
  return current
    ? sortRecipeCatalog(matched, current.id as RecipeCatalogSortKey, current.desc)
    : matched
})

const pageSize = ref('50')
const page = ref(1)
const { pageCount, pageStart, pageEnd, pagedRows } = usePagedRows(
  sortedRows, () => Number.parseInt(pageSize.value, 10), page
)
watch([query, sourceFilter, sorting, pageSize, cacheKey], () => {
  page.value = 1
})

const tableUi = {
  tr: 'cursor-pointer transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 whitespace-nowrap overflow-hidden text-ellipsis tabular-nums sk-value',
  th: 'py-2 px-3 sk-label'
}

const dash = (value: string | null) => value ?? '—'

// Only Provision ships the pre-split name; VeritySEM answers '' for all three.
const splitColumns: TableColumn<RecipeUsageCatalogRow>[] = props.toolType === 'provision'
  ? [
      { accessorKey: 'product_id', header: 'Product' },
      { accessorKey: 'layer_id', header: 'Layer' },
      { accessorKey: 'recipe_name', header: 'Recipe name' }
    ]
  : []

const columns = computed<TableColumn<RecipeUsageCatalogRow>[]>(() => [
  { accessorKey: 'recipe_id', header: 'recipe_id' },
  ...splitColumns,
  ...(props.fabs.length > 1 ? [{ accessorKey: 'fab_name', header: 'Fab' }] : []),
  { id: 'tool_count', accessorFn: row => row.eqp_ids.length, header: '장비 수' },
  { accessorKey: 'n_uses', header: '누적 사용', cell: ({ row }) => row.original.n_uses.toLocaleString() },
  { accessorKey: 'first_used', header: '최초 사용', cell: ({ row }) => dash(row.original.first_used) },
  { accessorKey: 'last_used', header: '최근 사용', cell: ({ row }) => dash(row.original.last_used) },
  { accessorKey: 'source', header: '출처' }
])

const downloadCatalog = () => downloadTable(
  `${props.toolType}-${(props.fabs.join('+') || 'all').toLowerCase()}-recipe-list-${todayStamp()}.xlsx`,
  ['recipe_id', 'fab_name', 'product_id', 'layer_id', 'recipe_name', 'eqp_ids', 'n_uses', 'first_used', 'last_used', 'source'],
  sortedRows.value.map(row => [
    row.recipe_id, row.fab_name, row.product_id, row.layer_id, row.recipe_name,
    row.eqp_ids.join(', '), row.n_uses, row.first_used ?? '', row.last_used ?? '', row.source
  ])
)
</script>
