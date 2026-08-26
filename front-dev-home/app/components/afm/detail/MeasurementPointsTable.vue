<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-0', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-target"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Measurement points
          </h2>
          <span class="sk-meta tabular-nums">
            ({{ filteredRows.length }} / {{ data.length }})
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            v-for="point in availablePoints"
            :key="point"
            type="button"
            class="inline-flex h-6 items-center rounded-md px-2 text-xs font-medium ring-1 transition-colors"
            :class="chipClass(selectedPoint === point)"
            @click="$emit('update:selectedPoint', point)"
          >
            {{ point }}
          </button>
          <button
            v-if="selectedPoint"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs text-(--sk-ink-muted) ring-1 ring-zinc-200 hover:bg-zinc-50 dark:ring-zinc-700 dark:hover:bg-zinc-800"
            @click="$emit('update:selectedPoint', '')"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
            All
          </button>
        </div>
      </div>
    </template>

    <div class="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-4 py-2.5 dark:border-zinc-800/60">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        size="xs"
        placeholder="Search rows…"
        class="w-44"
      />
      <USelectMenu
        v-model="visibleKeys"
        :items="columnItems"
        value-key="value"
        multiple
        size="xs"
        icon="i-lucide-columns-3"
        placeholder="Columns"
        class="min-w-40"
        :search-input="{ placeholder: 'Filter columns…' }"
      />
      <div class="ml-auto flex items-center gap-3 sk-meta tabular-nums">
        <span>Total <b class="text-(--sk-ink)">{{ summary.total }}</b></span>
        <span>Valid <b class="text-(--sk-ink)">{{ summary.valid }}</b></span>
        <span>Cols <b class="text-(--sk-ink)">{{ visibleColumns.length }}</b></span>
      </div>
    </div>

    <div
      v-if="filteredRows.length === 0"
      class="px-4 py-10 text-center sk-body"
    >
      No measurement rows
    </div>
    <template v-else>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px] font-mono">
          <thead class="bg-zinc-50/95 text-(--sk-ink-muted) dark:bg-zinc-900/90">
            <tr>
              <th
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-2.5 py-1.5 text-right sk-label first:text-left"
              >
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in pagedRows"
              :key="i"
              class="border-t border-zinc-100 transition-colors hover:bg-zinc-50/80 dark:border-zinc-800/60 dark:hover:bg-zinc-800/30"
            >
              <td
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-2.5 py-1 text-right sk-value-num first:text-left"
              >
                {{ formatCell(row[col.key]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        v-if="filteredRows.length > PAGE_SIZE"
        class="flex justify-center border-t border-zinc-100 px-4 py-2 dark:border-zinc-800/60"
      >
        <UPagination
          v-model:page="page"
          :total="filteredRows.length"
          :items-per-page="PAGE_SIZE"
          :sibling-count="1"
          size="xs"
        />
      </div>
    </template>
  </UCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import { chipClass } from '~/utils/chipClass'

const props = defineProps<{
  data: AfmDetailRow[]
  availablePoints: string[]
  selectedPoint: string
}>()

defineEmits<{
  (event: 'update:selectedPoint', point: string): void
}>()

const PAGE_SIZE = 25
const STORAGE_KEY = 'skewnono:afm.pointColumns'

const search = ref('')
const page = ref(1)
const visibleKeys = ref<string[]>([])

const allColumns = computed(() => derivePointColumns(props.data))
const columnItems = computed(() => allColumns.value.map(c => ({ label: c.label, value: c.key })))
const visibleColumns = computed(() => allColumns.value.filter(c => visibleKeys.value.includes(c.key)))

const loadStoredKeys = (): string[] | null => {
  if (!import.meta.client) return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === 'string') : null
  } catch {
    return null
  }
}

let initialized = false
watch(allColumns, (cols) => {
  if (initialized || cols.length === 0) return
  const present = new Set(cols.map(c => c.key))
  const stored = (loadStoredKeys() ?? []).filter(k => present.has(k))
  visibleKeys.value = stored.length
    ? stored
    : DEFAULT_POINT_COLUMN_KEYS.filter(k => present.has(k))
  initialized = true
}, { immediate: true })

watch(visibleKeys, (keys) => {
  if (!import.meta.client) return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
  } catch {
    // ignore persistence failures (private mode, quota)
  }
}, { deep: true })

const filteredRows = computed(() =>
  filterPointRows(props.data, props.selectedPoint, search.value, visibleKeys.value)
)
const pagedRows = computed(() => pagePointRows(filteredRows.value, page.value, PAGE_SIZE))
const summary = computed(() => pointsSummary(filteredRows.value))

// Reset to page 1 whenever the row set or any filter changes. `() => props.data`
// covers the router reusing this instance across measurement navigations.
watch([() => props.data, () => props.selectedPoint, search, visibleKeys], () => {
  page.value = 1
})

const formatCell = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}
</script>
