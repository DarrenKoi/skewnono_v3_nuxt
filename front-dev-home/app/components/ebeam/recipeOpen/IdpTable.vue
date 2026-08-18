<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex items-start justify-between gap-3 border-b border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
      <div>
        <p class="sk-eyebrow text-(--sk-brand)">
          IDP_IMAGE_INFO
        </p>
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p class="mt-0.5 sk-title">
            파라미터 목록 · {{ rows.length }}
          </p>
          <EbeamRecipeStatusInlineSummary :items="summaryItems" />
        </div>
      </div>
      <div class="flex flex-col items-end gap-1.5">
        <span class="sk-meta">
          행 클릭 → 우측 상세 표시
        </span>
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
    <div class="min-h-0 flex-1 overflow-auto">
      <table class="w-full border-collapse font-mono text-[12px]">
        <thead>
          <tr class="sticky top-0 z-10 bg-zinc-50/80 text-left text-(--sk-ink-muted) dark:bg-zinc-900/60">
            <th class="w-1 p-0" />
            <th
              v-for="column in columns"
              :key="column.key"
              :aria-sort="ariaSort(column.key)"
              class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1"
                @click="applySort(column.key)"
              >
                <UIcon
                  :name="sortIcon(column.key)"
                  class="h-3.5 w-3.5"
                />
                <span>{{ column.label }}</span>
              </button>
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
              class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-900 dark:border-zinc-800/60 dark:text-zinc-100"
              :class="item.sourceIndex === selectedIndex ? 'font-bold' : 'font-semibold'"
            >
              {{ item.row.Parameter }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ item.row.SEQ }}/{{ item.row.Last_SEQ }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ item.row.Region }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <EbeamRecipeOpenBoolPill :value="item.row.Addressing" />
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <EbeamRecipeOpenBoolPill :value="item.row.Mother_Para" />
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <EbeamRecipeOpenBoolPill :value="item.row.Double_Addressing" />
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ item.row.Meas_Counting }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <!-- True = 데이터가 legacy 로 나가지 않음. ok-when=false 라야 그 행이
                   컬럼에서 눈에 띄는 예외로 읽힙니다. -->
              <EbeamRecipeOpenBoolPill
                :value="item.row.dnumber_removed"
                :ok-when="false"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import {
  DEFAULT_RECIPE_OPEN_SORT,
  buildRecipeOpenSummaryItems,
  nextRecipeOpenSort,
  recipeOpenRowKey,
  sortRecipeOpenRows,
  type RecipeOpenSortDirection,
  type RecipeOpenSortKey
} from '~/utils/recipeOpenTable'

const props = defineProps<{
  rows: IdpImageInfoRow[]
  measurementPointCount: number
  alignPointCount: number
}>()

defineEmits<{
  openAlign: []
}>()

const selectedIndex = defineModel<number>('selectedIndex', { required: true })

const columns: readonly { key: RecipeOpenSortKey, label: string }[] = [
  { key: 'Parameter', label: 'Parameter' },
  { key: 'SEQ', label: 'SEQ' },
  { key: 'Region', label: 'Region' },
  { key: 'Addressing', label: 'Addressing' },
  { key: 'Mother_Para', label: 'Mother' },
  { key: 'Double_Addressing', label: 'Double' },
  { key: 'Meas_Counting', label: 'Cnt' },
  { key: 'dnumber_removed', label: 'd# 제거' }
]

const sortKey = ref<RecipeOpenSortKey>(DEFAULT_RECIPE_OPEN_SORT.key)
const sortDirection = ref<RecipeOpenSortDirection>(DEFAULT_RECIPE_OPEN_SORT.direction)
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
