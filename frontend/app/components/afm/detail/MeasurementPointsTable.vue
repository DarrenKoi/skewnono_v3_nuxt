<template>
  <AfmCard
    icon="i-lucide-table"
    title="측정 포인트"
    :count="filteredRows.length"
    flush
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2">
        <SkChip
          size="sm"
          icon="i-lucide-crosshair"
          :label="selectedPoint ? `${selectedPoint}만` : '선택 포인트만'"
          :active="onlySelected"
          :disabled="!selectedPoint"
          @click="onlySelected = !onlySelected"
        />
        <UInput
          v-model="search"
          icon="i-lucide-search"
          size="sm"
          placeholder="행 검색"
          aria-label="행 검색"
          class="w-44"
        />
        <USelectMenu
          v-model="visibleKeys"
          :items="columnItems"
          value-key="value"
          multiple
          size="sm"
          icon="i-lucide-columns-3"
          placeholder="컬럼"
          class="w-48"
          :search-input="{ placeholder: '컬럼 검색' }"
        />
        <p class="sk-meta">
          유효 <b class="font-mono text-[13px] font-semibold tabular-nums text-(--sk-ink)">{{ validCount }}</b>
          / <span class="font-mono text-[13px] tabular-nums text-(--sk-ink)">{{ filteredRows.length }}</span>
        </p>
      </div>
    </template>

    <p
      v-if="filteredRows.length === 0"
      class="px-4 py-10 text-center sk-body"
    >
      표시할 측정 포인트가 없습니다.
    </p>
    <template v-else>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-(--sk-border) bg-(--sk-muted-surface)">
              <th
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-4 py-2 text-right text-xs font-semibold whitespace-nowrap text-(--sk-ink-muted) first:text-left"
              >
                {{ col.label }}
              </th>
              <!-- Trailing spacer: the columns pack left at their own width
                   instead of spreading a 1800px row into far-apart numbers. -->
              <th class="w-full" />
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border-soft)">
            <!-- A row picks its point for the 포인트 분석 cards above; the picked
                 point's rows keep the accent wash with the header-menu's 2px left
                 edge (DESIGN.md §Navigation), so table and charts name one point. -->
            <tr
              v-for="(row, i) in pagedRows"
              :key="i"
              class="cursor-pointer transition-colors duration-200"
              :class="row.measurement_point === selectedPoint
                ? 'bg-(--sk-accent-tint) shadow-[inset_2px_0_0_var(--sk-accent)]'
                : 'hover:bg-(--sk-muted-surface)'"
              :aria-selected="row.measurement_point === selectedPoint"
              @click="selectedPoint = String(row.measurement_point)"
            >
              <td
                v-for="col in visibleColumns"
                :key="col.key"
                class="px-4 py-1.5 text-right font-mono text-[13px] whitespace-nowrap tabular-nums text-(--sk-ink) first:text-left first:font-semibold"
              >
                {{ formatCell(row[col.key]) }}
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>
      <div
        v-if="filteredRows.length > PAGE_SIZE"
        class="flex justify-center border-t border-(--sk-border-soft) px-4 py-2"
      >
        <UPagination
          v-model:page="page"
          :total="filteredRows.length"
          :items-per-page="PAGE_SIZE"
          :sibling-count="1"
          size="sm"
        />
      </div>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  data: AfmDetailRow[]
}>()

// The point the 포인트 분석 cards are drawn for. The table lists every point
// unless 선택 포인트만 narrows it; clicking a row picks that row's point.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })
const onlySelected = ref(false)

const PAGE_SIZE = 25

const search = ref('')
const page = ref(1)

const allColumns = computed(() => derivePointColumns(props.data))
const columnItems = computed(() => allColumns.value.map(c => ({ label: c.label, value: c.key })))

// The column pick is shared by every measurement. Keys this file lacks are
// ignored, and an empty pick falls back to the defaults.
const storedKeys = usePersistedState<string[]>(
  'afm-point-columns',
  'skewnono:afm.pointColumns',
  { default: () => [], normalize: normalizeStringArray }
)
const visibleKeys = computed({
  get: () => {
    const present = allColumns.value.map(c => c.key)
    const picked = storedKeys.value.filter(k => present.includes(k))
    return picked.length ? picked : defaultPointColumnKeys(allColumns.value)
  },
  set: (keys: string[]) => {
    storedKeys.value = keys
  }
})
const visibleColumns = computed(() => allColumns.value.filter(c => visibleKeys.value.includes(c.key)))

const filteredRows = computed(() =>
  filterPointRows(props.data, onlySelected.value ? selectedPoint.value : '', search.value, visibleKeys.value)
)
const pagedRows = computed(() => pagePointRows(filteredRows.value, page.value, PAGE_SIZE))
const validCount = computed(() => pointsSummary(filteredRows.value).valid)

// Back to page 1 whenever the row set changes — but not when a row click only
// moves the highlight, or the clicked row would jump off the page.
watch(
  () => [props.data, onlySelected.value && selectedPoint.value, search.value, visibleKeys.value.join('|')],
  () => {
    page.value = 1
  }
)
watch(selectedPoint, (next) => {
  if (!next) onlySelected.value = false
})

const formatCell = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}
</script>
