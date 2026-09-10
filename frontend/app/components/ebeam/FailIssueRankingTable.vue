<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          {{ title }}
        </h3>
        <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-xs tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
        </span>
        <!-- Badges that only one panel needs (e.g. the TAT view's server-side
             row cap) go here rather than becoming another prop. -->
        <slot name="title-extra" />
        <EbeamRecipeStatusInlineSummary
          v-if="summaryItems?.length"
          :items="summaryItems"
        />
      </div>
      <div class="flex items-center gap-2">
        <UInput
          v-model="search"
          size="xs"
          :placeholder="searchPlaceholder"
          icon="i-lucide-search"
          class="w-[12rem]"
        />
        <USelect
          v-model="pageSize"
          class="w-[6.5rem]"
          size="xs"
          :items="pageSizeOptions"
        />
        <UTooltip text="클립보드 복사">
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            aria-label="표를 클립보드에 복사"
            :disabled="sortedRows.length === 0"
            @click="emitCopy"
          />
        </UTooltip>
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          :label="downloadLabel"
          :disabled="sortedRows.length === 0"
          @click="emitDownload"
        />
      </div>
    </div>

    <UTable
      v-model:sorting="sorting"
      :columns="columns"
      :data="pagedRows"
      :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
      sticky="header"
      :ui="tableUi"
    >
      <template
        v-for="id in sortableIds"
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

      <!-- Forward parent-provided cell slots (e.g. #actions-cell) so panels
           can add per-row controls without widening this component's API.
           `title-extra` is ours and renders in the header, so it must not be
           handed to UTable as well. -->
      <template
        v-for="(_, name) in tableSlots"
        :key="name"
        #[name]="slotProps"
      >
        <slot
          :name="name"
          v-bind="slotProps"
        />
      </template>
    </UTable>

    <div class="mt-2 flex items-center justify-between sk-meta">
      <span class="tabular-nums">
        Page {{ page }} / {{ pageCount }}
        <span class="ml-2 text-(--sk-ink-muted)">
          {{ pageStart }}–{{ pageEnd }} of {{ filteredRows.length.toLocaleString() }}
        </span>
      </span>
      <div class="flex gap-1">
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-chevron-left"
          :disabled="page <= 1"
          @click="page -= 1"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          trailing-icon="i-lucide-chevron-right"
          :disabled="page >= pageCount"
          @click="page += 1"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends object">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { RecipeStatusSummaryItem } from '~/utils/recipeStatusSummary'
import type { RankingTableState } from '~/utils/rankingTable'

// Generic ranking table — Align (by eqp_id) and Meas (by recipe) panels
// share the same pagination/sort/search/Excel machinery and only differ in
// columns and which row fields drive the filter. Pulling this out keeps
// FailIssueView focused on layout instead of repeating table boilerplate.
const props = defineProps<{
  title: string
  summaryItems?: readonly RecipeStatusSummaryItem[]
  searchPlaceholder: string
  rows: readonly T[]
  columns: TableColumn<T>[]
  sortableIds: readonly string[]
  defaultSortId: string
  // Returned true if a row matches the lowercased search term. Owned by
  // the parent so the search columns can stay typed per panel.
  searchPredicate: (row: T, term: string) => boolean
  resetKey?: unknown
  downloadLabel?: string
}>()

const emit = defineEmits<{
  'download': [rows: T[]]
  'copy': [rows: T[]]
  // See RankingTableState — panels that render beside the table need the view
  // it is showing, not just the rows they handed in.
  'update:state': [state: RankingTableState<T>]
}>()

const downloadLabel = computed(() => props.downloadLabel ?? 'Excel')

// `title-extra` is ours and renders in the header, so it must not also be
// handed to UTable by the passthrough below.
const slots = useSlots()
const tableSlots = computed(() =>
  Object.fromEntries(Object.entries(slots).filter(([name]) => name !== 'title-extra'))
)

const pageSizeOptions = PAGE_SIZE_OPTIONS

const search = ref('')
const pageSize = ref('25')
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const page = ref(1)
const sorting = ref<SortingState>([{ id: props.defaultSortId, desc: true }])

// 헤더에 배경을 주지 않는 이유는 RecipeTatFleetTable.vue의 같은 블록에 있습니다:
// sticky 헤더가 이미 테마 surface 위에 앉아 있습니다. 타입은 .sk-label에 맡깁니다.
const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 whitespace-nowrap overflow-hidden text-ellipsis tabular-nums sk-value',
  th: 'py-2 px-3 sk-label'
}

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const getSortableNumber = (row: T, id: string) => {
  const value = (row as Record<string, unknown>)[id]
  return typeof value === 'number' ? value : 0
}

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return [...props.rows]
  return props.rows.filter(r => props.searchPredicate(r, q))
})

const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id
  const dir = current.desc ? -1 : 1
  return [...filteredRows.value].sort((a, b) => {
    const av = getSortableNumber(a, id)
    const bv = getSortableNumber(b, id)
    return (av - bv) * dir
  })
})

const { pageCount, pageStart, pageEnd, pagedRows } = usePagedRows(
  sortedRows, pageSizeNumber, page
)

// Reset to page 1 on any user filter/sort change or when the parent
// signals scope change via resetKey.
watch([search, pageSize, sorting, () => props.resetKey], () => {
  page.value = 1
})

// `immediate` so a listening parent is populated on first render rather than
// staying empty until the user touches a sort header.
watch(
  [search, sorting, sortedRows],
  ([term, sort, rows]) => emit('update:state', {
    search: term,
    sorting: sort,
    sortedRows: rows
  }),
  { immediate: true }
)

const emitDownload = () => {
  emit('download', sortedRows.value)
}

const emitCopy = () => {
  emit('copy', sortedRows.value)
}
</script>
