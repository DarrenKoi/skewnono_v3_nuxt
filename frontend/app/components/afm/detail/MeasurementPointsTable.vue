<template>
  <AfmCard
    icon="i-lucide-target"
    title="측정 포인트"
    :count="filteredRows.length"
    flush
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-1.5">
        <SkChip
          size="sm"
          tone="ink"
          label="전체"
          :active="!selectedPoint"
          @click="selectedPoint = ''"
        />
        <SkChip
          v-for="point in availablePoints"
          :key="point"
          size="sm"
          tone="ink"
          :label="point"
          :active="selectedPoint === point"
          @click="selectedPoint = point"
        />
      </div>
    </template>

    <div class="flex flex-wrap items-center gap-2 border-b border-(--sk-border-soft) px-4 py-2.5">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        size="xs"
        placeholder="행 검색"
        class="w-44"
      />
      <USelectMenu
        v-model="visibleKeys"
        :items="columnItems"
        value-key="value"
        multiple
        size="xs"
        icon="i-lucide-columns-3"
        placeholder="컬럼"
        class="min-w-40"
        :search-input="{ placeholder: '컬럼 검색' }"
      />
      <p class="ml-auto sk-meta">
        유효 <b class="sk-value-num">{{ validCount }}</b>
      </p>
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
                class="whitespace-nowrap px-2.5 py-1.5 text-right sk-label first:text-left"
              >
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border-soft)">
            <tr
              v-for="(row, i) in pagedRows"
              :key="i"
              class="transition-colors duration-200 hover:bg-(--sk-muted-surface)"
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
        class="flex justify-center border-t border-(--sk-border-soft) px-4 py-2"
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
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  data: AfmDetailRow[]
  availablePoints: string[]
}>()

// '' = every point. The pick is also the subject of the profile cards beside this one.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

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
  filterPointRows(props.data, selectedPoint.value, search.value, visibleKeys.value)
)
const pagedRows = computed(() => pagePointRows(filteredRows.value, page.value, PAGE_SIZE))
const validCount = computed(() => pointsSummary(filteredRows.value).valid)

// Back to page 1 whenever the row set changes.
watch(filteredRows, () => {
  page.value = 1
})

const formatCell = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}
</script>
