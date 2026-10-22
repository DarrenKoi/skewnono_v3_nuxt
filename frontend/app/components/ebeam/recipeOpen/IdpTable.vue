<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex items-start justify-between gap-3 border-b border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
      <div>
        <p class="sk-eyebrow text-(--sk-brand)">
          IDP_IMAGE_INFO
        </p>
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p class="mt-0.5 sk-title whitespace-nowrap">
            파라미터 목록 · {{ rows.length }}
          </p>
          <EbeamRecipeStatusInlineSummary :items="summaryItems" />
        </div>
      </div>
      <div class="flex flex-col items-end gap-1.5">
        <span class="sk-meta">
          행 클릭 → 우측 상세 표시
        </span>
        <div class="flex items-center gap-1">
          <!-- Shown columns are a per-user preference: Addressing, Double,
               d# 제거 mean nothing to some readers, and P_No / D_No (off by
               default) come from wafer_mp_info, joined by Parameter. -->
          <USelectMenu
            v-model="visibleColumns"
            :items="columnItems"
            value-key="value"
            multiple
            size="xs"
            icon="i-lucide-columns-3"
            aria-label="표시 컬럼 선택"
            class="w-32"
          >
            <span class="truncate">
              컬럼 {{ visibleColumns.length }} / {{ columnItems.length }}
            </span>
          </USelectMenu>
          <!-- Recipe-scoped, so it sits with the recipe-scoped table rather
               than in the SELECTED header: every parameter row and every
               measurement location, no images, no tool reads. -->
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-file-down"
            label="Excel (전체)"
            class="rounded-lg font-semibold"
            :loading="exporting"
            title="모든 parameter 행과 측정 위치를 시트 두 장으로 내려받습니다"
            @click="$emit('exportAll')"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-eye"
            label="Align 정보"
            class="rounded-lg font-semibold"
            @click="$emit('openAlign')"
          />
        </div>
      </div>
    </div>
    <div class="min-h-0 flex-1 overflow-auto">
      <table class="w-full border-collapse font-mono text-[12px]">
        <thead>
          <tr class="sticky top-0 z-10 bg-zinc-50/80 text-left text-(--sk-ink-muted) dark:bg-zinc-900/60">
            <th class="w-1 p-0" />
            <th
              v-for="column in shownColumns"
              :key="column.key"
              :aria-sort="column.sortKey ? ariaSort(column.sortKey) : undefined"
              class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800"
            >
              <button
                v-if="column.sortKey"
                type="button"
                class="inline-flex items-center gap-1"
                @click="applySort(column.sortKey)"
              >
                <UIcon
                  :name="sortIcon(column.sortKey)"
                  class="h-3.5 w-3.5"
                />
                <span>{{ column.label }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in displayedRows"
            :key="recipeOpenRowKey(item)"
            class="cursor-pointer transition-colors"
            :class="item.sourceIndex === selectedIndex
              ? 'bg-(--sk-brand-soft)/55'
              : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/40'"
            @click="selectedIndex = item.sourceIndex"
          >
            <td
              class="w-1 p-0"
              :class="item.sourceIndex === selectedIndex ? 'bg-(--sk-brand)' : ''"
            />
            <td
              v-for="column in shownColumns"
              :key="column.key"
              class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60"
              :class="column.key === 'Parameter'
                ? ['text-zinc-900 dark:text-zinc-100', item.sourceIndex === selectedIndex ? 'font-bold' : 'font-semibold']
                : 'text-zinc-600 dark:text-zinc-300'"
            >
              <template v-if="column.key === 'Parameter'">
                <template v-if="item.row.Parameter">
                  {{ item.row.Parameter }}
                </template>
                <span
                  v-else
                  class="text-xs font-normal text-(--sk-ink-subtle)"
                >(이름 없음)</span>
              </template>
              <span
                v-else-if="column.key === 'P_No' || column.key === 'D_No'"
                :title="pointNumbers(item.row, column.key).join(', ')"
              >{{ shortList(pointNumbers(item.row, column.key)) }}</span>
              <template v-else-if="column.key === 'SEQ'">
                {{ item.row.SEQ }}/{{ item.row.Last_SEQ }}
              </template>
              <!-- True = 데이터가 legacy 로 나가지 않음. ok-when=false 라야 그 행이
                   컬럼에서 눈에 띄는 예외로 읽힙니다. -->
              <EbeamRecipeOpenBoolPill
                v-else-if="column.key === 'dnumber_removed'"
                :value="item.row.dnumber_removed"
                :ok-when="false"
              />
              <EbeamRecipeOpenBoolPill
                v-else-if="typeof item.row[column.key] === 'boolean'"
                :value="item.row[column.key] as boolean"
              />
              <template v-else>
                {{ item.row[column.key] }}
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IdpImageInfoRow, WaferMpInfoRow } from '~/composables/useRecipeSearchApi'
import {
  DEFAULT_IDP_COLUMNS,
  DEFAULT_RECIPE_OPEN_SORT,
  IDP_OPTIONAL_COLUMNS,
  normalizeIdpColumns,
  pointNumbersOf,
  type IdpColumnKey,
  buildRecipeOpenSummaryItems,
  nextRecipeOpenSort,
  recipeOpenRowKey,
  sortRecipeOpenRows,
  type RecipeOpenSortDirection,
  type RecipeOpenSortKey
} from '~/utils/recipeOpenTable'

const props = defineProps<{
  rows: IdpImageInfoRow[]
  /** wafer_mp_info — the source of the optional P_No / D_No columns. */
  mpRows: WaferMpInfoRow[]
  measurementPointCount: number
  alignPointCount: number
  exporting?: boolean
}>()

defineEmits<{
  openAlign: []
  exportAll: []
}>()

const selectedIndex = defineModel<number>('selectedIndex', { required: true })

const columnItems = IDP_OPTIONAL_COLUMNS.map(column => ({ label: column.label, value: column.key }))
// isEmpty off: a user who hides every optional column keeps that on reload,
// rather than having the factory delete the key and restore the defaults.
const visibleColumns = usePersistedState<IdpColumnKey[]>(
  'recipe-open-idp-columns',
  'skewnono:recipeOpen.idpColumns',
  { default: () => [...DEFAULT_IDP_COLUMNS], normalize: normalizeIdpColumns, isEmpty: () => false }
)
// Parameter first and always; the rest in catalogue order, not pick order.
// P_No / D_No are not idp_image_info fields, so they do not sort.
const shownColumns = computed(() => [
  { key: 'Parameter' as const, label: 'Parameter', sortKey: 'Parameter' as RecipeOpenSortKey },
  ...IDP_OPTIONAL_COLUMNS
    .filter(column => visibleColumns.value.includes(column.key))
    .map(column => ({
      ...column,
      sortKey: column.key === 'P_No' || column.key === 'D_No' ? null : column.key
    }))
])

const pointsByParameter = computed(() => pointNumbersOf(props.mpRows))
const pointNumbers = (row: IdpImageInfoRow, key: 'P_No' | 'D_No') => {
  const entry = pointsByParameter.value.get(row.Parameter ?? '')
  return (key === 'P_No' ? entry?.pNo : entry?.dNo) ?? []
}
// D_No varies per point, so a long list is cut; the cell's title has it whole.
const shortList = (values: readonly number[]) => values.length > 3
  ? `${values.slice(0, 3).join(', ')} …+${values.length - 3}`
  : values.join(', ')

const sortKey = ref<RecipeOpenSortKey>(DEFAULT_RECIPE_OPEN_SORT.key)
const sortDirection = ref<RecipeOpenSortDirection>(DEFAULT_RECIPE_OPEN_SORT.direction)
// Hiding the sorted column would leave an order nothing on screen explains, so
// it falls back to the default — SEQ asc, the table's own order even if hidden.
watch(shownColumns, (columns) => {
  if (columns.some(column => column.sortKey === sortKey.value)) return
  sortKey.value = DEFAULT_RECIPE_OPEN_SORT.key
  sortDirection.value = DEFAULT_RECIPE_OPEN_SORT.direction
})
const displayedRows = computed(() => sortRecipeOpenRows(
  props.rows,
  sortKey.value,
  sortDirection.value
))
const summaryItems = computed(() => buildRecipeOpenSummaryItems(
  props.measurementPointCount,
  props.alignPointCount
))

const applySort = (requestedKey: RecipeOpenSortKey) => {
  const nextSort = nextRecipeOpenSort(sortKey.value, sortDirection.value, requestedKey)
  sortKey.value = nextSort.key
  sortDirection.value = nextSort.direction
}

const ariaSort = (key: RecipeOpenSortKey) => {
  if (key !== sortKey.value) return 'none'
  return sortDirection.value === 'asc' ? 'ascending' : 'descending'
}

const sortIcon = (key: RecipeOpenSortKey) => {
  if (key !== sortKey.value) return 'i-lucide-arrow-up-down'
  return sortDirection.value === 'asc'
    ? 'i-lucide-arrow-up-narrow-wide'
    : 'i-lucide-arrow-down-wide-narrow'
}
</script>
