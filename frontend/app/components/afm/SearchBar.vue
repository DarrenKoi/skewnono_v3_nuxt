<template>
  <div class="space-y-6">
    <form
      class="dashboard-surface space-y-3 rounded-(--sk-r-card) p-4"
      @submit.prevent="commitSearch"
    >
      <div class="flex items-center gap-2">
        <UInput
          v-model="query"
          type="search"
          size="lg"
          icon="i-lucide-search"
          autocomplete="off"
          placeholder="Lot ID, Recipe, 날짜로 검색 (예: CMP, T7HQR42TA, 250609)"
          aria-label="AFM 측정 검색"
          class="min-w-0 flex-1"
        />
        <UButton
          type="submit"
          size="lg"
          color="primary"
          icon="i-lucide-search"
          label="검색"
        />
      </div>
      <!-- Recent terms sit in the open rather than behind an icon: one click
           re-runs a search, and the active one shows which search is on. -->
      <div
        v-if="recentTerms.length"
        class="flex flex-wrap items-center gap-1.5"
      >
        <span class="mr-1 inline-flex items-center gap-1 sk-meta">
          <UIcon
            name="i-lucide-history"
            class="size-3.5"
          />
          최근 검색어
        </span>
        <SkChip
          v-for="term in recentTerms"
          :key="term"
          size="sm"
          :label="term"
          :active="activeQuery === term"
          @click="activeQuery === term ? clearSearch() : applyTerm(term)"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          label="지우기"
          @click="cart.clearRecentSearches"
        />
      </div>
    </form>

    <AfmCard
      icon="i-lucide-database"
      :title="activeQuery ? '검색 결과' : '최근 측정'"
      :count="filteredResults.length"
      flush
    >
      <template #actions>
        <div class="flex items-center gap-3">
          <p
            v-if="activeQuery"
            class="sk-meta"
          >
            "<b class="font-semibold text-(--sk-ink)">{{ activeQuery }}</b>" 검색 결과
          </p>
          <UInput
            v-model="innerFilter"
            type="search"
            size="sm"
            icon="i-lucide-filter"
            placeholder="결과 내 필터"
            aria-label="결과 내 필터"
            class="w-52"
          />
        </div>
      </template>

      <AppLoadingState
        v-if="pending"
        variant="inline"
        class="h-40"
        title="측정 목록을 불러오는 중입니다."
      />
      <p
        v-else-if="error"
        class="px-4 py-10 text-center text-sm text-rose-600 dark:text-rose-400"
      >
        측정 목록을 불러오지 못했습니다.
      </p>
      <p
        v-else-if="!filteredResults.length"
        class="px-4 py-10 text-center sk-body"
      >
        표시할 측정이 없습니다.
      </p>
      <!-- A container query, not a viewport breakpoint: the card's own width
           decides whether the row fits as aligned columns (the header names each
           value once) or wraps into the stacked summary the side lists use. -->
      <div
        v-else
        class="@container max-h-[680px] overflow-y-auto"
      >
        <div
          :class="ROW_GRID"
          class="sticky top-0 z-10 hidden border-b border-(--sk-border) bg-(--sk-surface) px-4 py-2 text-xs font-semibold whitespace-nowrap text-(--sk-ink-muted) @4xl:grid"
          aria-hidden="true"
        >
          <span>측정 일시</span>
          <span>Recipe</span>
          <span>Lot</span>
          <span>Slot</span>
          <span>측정</span>
          <span>데이터</span>
          <span class="text-right">그룹</span>
        </div>
        <ul class="divide-y divide-(--sk-border-soft)">
          <li
            v-for="result in filteredResults"
            :key="result.filename"
            class="group cursor-pointer px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
            @click="$emit('view-details', result)"
          >
            <!-- Wide: one aligned row under the header. -->
            <div
              :class="ROW_GRID"
              class="hidden items-center @4xl:grid"
            >
              <span class="font-mono text-[13px] tabular-nums text-(--sk-ink)">
                {{ result.formattedDate }}
              </span>
              <button
                type="button"
                class="flex min-w-0 items-center gap-1.5 text-left"
                :title="result.filename"
                @click.stop="$emit('view-details', result)"
              >
                <span class="truncate text-sm font-semibold text-(--sk-ink) group-hover:underline">
                  {{ result.recipeName }}
                </span>
              </button>
              <span class="truncate font-mono text-[13px] font-medium tabular-nums text-(--sk-ink)">
                {{ result.lotId }}
              </span>
              <span class="font-mono text-[13px] font-medium tabular-nums text-(--sk-ink)">
                {{ result.slotNumber }}
              </span>
              <span class="truncate text-[13px] text-(--sk-ink)">
                {{ result.measuredInfo }}
              </span>
              <AfmDataAvailability :measurement="result" />
              <div class="flex items-center justify-end gap-1">
                <AfmGroupToggle
                  :in-group="cart.isInGroup(result.filename)"
                  @toggle="toggleGroup(result)"
                />
                <UIcon
                  name="i-lucide-chevron-right"
                  class="size-4 text-(--sk-ink-subtle) transition-colors duration-200 group-hover:text-(--sk-ink)"
                />
              </div>
            </div>

            <!-- Narrow: the stacked summary, actions on the right. -->
            <div class="flex items-center gap-3 @4xl:hidden">
              <button
                type="button"
                class="min-w-0 flex-1 text-left"
                :title="result.filename"
                @click.stop="$emit('view-details', result)"
              >
                <AfmMeasurementSummary :measurement="result">
                  <AfmDataAvailability :measurement="result" />
                </AfmMeasurementSummary>
              </button>
              <AfmGroupToggle
                :in-group="cart.isInGroup(result.filename)"
                @toggle="toggleGroup(result)"
              />
            </div>
          </li>
        </ul>
      </div>
    </AfmCard>
  </div>
</template>

<script setup lang="ts">
import type { AfmMeasurement } from '~/composables/useAfmCart'

const props = defineProps<{
  toolId: string
}>()

defineEmits<{
  'view-details': [measurement: AfmMeasurement]
}>()

// 측정 일시 | Recipe | Lot | Slot | 측정 | 데이터 | 그룹 — shared by the header and every row.
const ROW_GRID = 'grid-cols-[10.5rem_minmax(0,1fr)_6rem_3rem_6.5rem_6.5rem_7rem] gap-x-3'

const cart = useAfmCart(props.toolId)
const recentTerms = cart.recentSearches
const { data: files, pending, error } = useAfmDetailApi().useAfmFiles(props.toolId.toUpperCase())

const query = ref('')
const activeQuery = ref('')
const innerFilter = ref('')

// The box's native clear button empties it; an empty box is no search.
watch(query, (next) => {
  if (!next) activeQuery.value = ''
})

const matchesTerm = (row: AfmMeasurement, term: string) =>
  [row.filename, row.recipeName, row.lotId, row.formattedDate, String(row.slotNumber), row.measuredInfo]
    .some(value => value.toLowerCase().includes(term))

const filteredResults = computed(() => {
  const terms = [activeQuery.value, innerFilter.value].map(t => t.toLowerCase().trim()).filter(Boolean)
  return (files.value ?? []).filter(row => terms.every(term => matchesTerm(row, term)))
})

const toggleGroup = (row: AfmMeasurement) =>
  cart.isInGroup(row.filename) ? cart.removeFromGroup(row.filename) : cart.addToGroup(row)

const commitSearch = () => {
  activeQuery.value = query.value.trim()
  cart.recordRecentSearch(activeQuery.value)
}

const applyTerm = (term: string) => {
  query.value = term
  activeQuery.value = term
}

const clearSearch = () => {
  query.value = ''
  activeQuery.value = ''
}
</script>
