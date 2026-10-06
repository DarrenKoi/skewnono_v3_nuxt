<template>
  <AfmCard
    icon="i-lucide-list"
    title="측정 포인트 표"
    flush
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2.5">
        <span class="sk-value-num text-sm">{{ filteredRows.length }} / {{ scopeTotal }}</span>
        <div class="flex gap-1">
          <SkChip
            tone="ink"
            label="전체"
            :active="scope === 'all'"
            @click="scope = 'all'"
          />
          <SkChip
            tone="ink"
            label="선택 포인트"
            :active="scope === 'point'"
            @click="scope = 'point'"
          />
        </div>
        <p class="sk-meta text-sm">
          유효 <b class="sk-value-num text-sm">{{ validCount }}</b>
        </p>
      </div>
    </template>

    <div class="flex flex-wrap items-center gap-x-3.5 gap-y-2 border-b border-(--sk-border-soft) px-4 py-2.5">
      <UInput
        v-model="search"
        type="search"
        icon="i-lucide-search"
        size="md"
        placeholder="행 검색 (보이는 컬럼)"
        aria-label="행 검색"
        class="w-64"
      />
      <div
        v-for="facet in facets"
        :key="facet.key"
        class="flex items-center gap-1"
      >
        <span class="mr-0.5 sk-meta">{{ facet.key }}</span>
        <SkChip
          label="전체"
          :active="!equals[facet.key]"
          @click="equals[facet.key] = ''"
        />
        <SkChip
          v-for="option in facet.options"
          :key="option.value"
          :label="option.label"
          :count="option.count"
          :active="equals[facet.key] === option.value"
          @click="equals[facet.key] = option.value"
        />
      </div>
      <UButton
        v-if="hasFilters"
        size="sm"
        color="neutral"
        variant="ghost"
        icon="i-lucide-rotate-ccw"
        label="필터 초기화"
        @click="resetFilters"
      />
      <!-- Labelled and counted rather than listing the picked names, which
           truncate to an unreadable "Point, X, Y, …" that hides what it is. -->
      <div class="ml-auto flex items-center gap-2">
        <span class="sk-meta">표시 컬럼</span>
        <USelectMenu
          v-model="visibleKeys"
          :items="columnItems"
          value-key="value"
          multiple
          size="md"
          icon="i-lucide-columns-3"
          aria-label="표시 컬럼 선택"
          class="w-48"
          :search-input="{ placeholder: '컬럼 검색' }"
        >
          <span class="truncate">
            컬럼 <b class="sk-value-num text-sm">{{ visibleKeys.length }}</b> / {{ columnItems.length }}
          </span>
        </USelectMenu>
      </div>
    </div>

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
            <tr class="border-b border-(--sk-border)">
              <th
                v-for="col in visibleColumns"
                :key="col.key"
                class="whitespace-nowrap px-3 py-2 text-right sk-label text-xs first:text-left"
              >
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border-soft)">
            <!-- A row is its point: clicking it, or Enter / Space on it, moves
                 the whole page there. -->
            <tr
              v-for="(row, i) in pagedRows"
              :key="i"
              tabindex="0"
              class="cursor-pointer transition-colors duration-200 hover:bg-(--sk-muted-surface)"
              :class="row.measurement_point === selectedPoint ? 'bg-(--sk-muted-surface)' : ''"
              @click="selectedPoint = row.measurement_point"
              @keydown.enter.space.prevent="selectedPoint = row.measurement_point"
            >
              <td
                v-for="col in visibleColumns"
                :key="col.key"
                class="whitespace-nowrap px-3 py-1.5 text-right sk-value-num text-sm first:text-left"
                :class="[
                  row.measurement_point === selectedPoint ? 'font-semibold' : '',
                  row[col.key] === false ? 'text-(--sk-bad)' : ''
                ]"
              >
                {{ formatPointCell(row[col.key]) }}
              </td>
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
  // Rows as the page tags them: with a `Block` column where a file has several.
  data: AfmDetailRow[]
}>()

// Picked in the rail; here it scopes the table and marks its rows.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const PAGE_SIZE = 25

// The table opens on the selected point, since the page is about that point;
// 전체 is one click away and keeps the point's rows marked.
const scope = ref<'all' | 'point'>('point')
const scopedPoint = computed(() => scope.value === 'point' ? selectedPoint.value : '')
const scopeTotal = computed(() => filterPointRows(props.data, { point: scopedPoint.value }).length)

const search = ref('')
const page = ref(1)

const allColumns = computed(() => derivePointColumns(props.data))
const columnItems = computed(() => allColumns.value.map(c => ({ label: c.label, value: c.key })))

// The column pick is shared by every measurement; resolvePointColumnKeys says
// what it means for a file whose columns differ.
const storedKeys = usePersistedState<string[]>(
  'afm-point-columns',
  'skewnono:afm.pointColumns',
  { default: () => [], normalize: normalizeStringArray }
)
const visibleKeys = computed({
  get: () => resolvePointColumnKeys(storedKeys.value, allColumns.value),
  set: (keys: string[]) => {
    storedKeys.value = mergePointColumnKeys(storedKeys.value, keys, allColumns.value)
  }
})
const visibleColumns = computed(() => allColumns.value.filter(c => visibleKeys.value.includes(c.key)))

// Exact-match filters per column; '' = not filtered. Block is offered only on a
// file that has more than one.
const equals = reactive<Record<string, string>>({})
const FACET_KEYS = ['State', 'Valid', 'Block']

const filters = computed(() => ({
  point: scopedPoint.value,
  search: search.value,
  visibleKeys: visibleKeys.value,
  equals
}))
const filteredRows = computed(() => filterPointRows(props.data, filters.value))

// Options are the values the file actually has; each count is what picking it
// would show with the other filters left as they are.
const facets = computed(() => FACET_KEYS
  .map((key) => {
    const values = [...new Set(props.data.filter(row => key in row).map(row => String(row[key])))]
    const counts = facetCounts(props.data, filters.value, key)
    return {
      key,
      options: values.map(value => ({
        value,
        label: key === 'Valid' ? value.toUpperCase() : value,
        count: counts.get(value) ?? 0
      }))
    }
  })
  .filter(facet => facet.options.length > 1))

const hasFilters = computed(() => !!search.value.trim() || FACET_KEYS.some(key => equals[key]))
const resetFilters = () => {
  search.value = ''
  for (const key of FACET_KEYS) equals[key] = ''
}

const { pagedRows } = usePagedRows(filteredRows, PAGE_SIZE, page)
const validCount = computed(() => filteredRows.value.filter(row => row.Valid === true).length)

// Back to page 1 whenever the row set changes.
watch(filteredRows, () => {
  page.value = 1
})
</script>
