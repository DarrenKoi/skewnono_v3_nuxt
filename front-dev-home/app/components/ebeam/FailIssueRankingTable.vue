<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          {{ title }}
        </h3>
        <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
        </span>
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
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          label="CSV"
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
           can add per-row controls without widening this component's API. -->
      <template
        v-for="(_, name) in $slots"
        :key="name"
        #[name]="slotProps"
      >
        <slot
          :name="name"
          v-bind="slotProps"
        />
      </template>
    </UTable>

    <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
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

// Generic ranking table — Align (by eqp_id) and Meas (by recipe) panels
// share the same pagination/sort/search/CSV machinery and only differ in
// columns and which row fields drive the filter. Pulling this out keeps
// FailIssueView focused on layout instead of repeating table boilerplate.
const props = defineProps<{
  title: string
  searchPlaceholder: string
  rows: readonly T[]
  columns: TableColumn<T>[]
  sortableIds: readonly string[]
  defaultSortId: string
  // Returned true if a row matches the lowercased search term. Owned by
  // the parent so the search columns can stay typed per panel.
  searchPredicate: (row: T, term: string) => boolean
  resetKey?: unknown
}>()

const emit = defineEmits<{
  download: [rows: T[]]
}>()

const search = ref('')
const pageSize = ref('25')
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))
const page = ref(1)
const sorting = ref<SortingState>([{ id: props.defaultSortId, desc: true }])

const pageSizeOptions = [
  { label: '25 / page', value: '25' },
  { label: '50 / page', value: '50' },
  { label: '100 / page', value: '100' }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
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

const pageCount = computed(
  () => Math.max(1, Math.ceil(sortedRows.value.length / pageSizeNumber.value))
)
const pageStart = computed(
  () => sortedRows.value.length === 0 ? 0 : ((page.value - 1) * pageSizeNumber.value) + 1
)
const pageEnd = computed(
  () => Math.min(page.value * pageSizeNumber.value, sortedRows.value.length)
)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSizeNumber.value
  return sortedRows.value.slice(start, start + pageSizeNumber.value)
})

// Reset to page 1 on any user filter/sort change or when the parent
// signals scope change via resetKey.
watch([search, pageSize, sorting, () => props.resetKey], () => {
  page.value = 1
})

const emitDownload = () => {
  emit('download', sortedRows.value)
}
</script>
