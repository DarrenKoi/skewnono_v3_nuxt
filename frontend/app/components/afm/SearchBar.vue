<template>
  <div class="space-y-6">
    <form
      class="dashboard-surface flex flex-wrap items-center gap-2 rounded-(--sk-r-card) p-4"
      @submit.prevent="commitSearch"
    >
      <UInput
        v-model="query"
        type="search"
        icon="i-lucide-search"
        autocomplete="off"
        placeholder="Lot ID, Recipe, 날짜로 검색 (예: CMP, T7HQR42TA, 250609)"
        aria-label="AFM 측정 검색"
        class="min-w-0 flex-1"
      />
      <UPopover v-if="recentTerms.length">
        <UButton
          type="button"
          color="neutral"
          variant="ghost"
          icon="i-lucide-history"
          aria-label="최근 검색어"
        />
        <template #content>
          <div class="w-64 p-2">
            <p class="px-2 pb-2 sk-label">
              최근 검색어
            </p>
            <UButton
              v-for="term in recentTerms"
              :key="term"
              block
              size="sm"
              color="neutral"
              variant="ghost"
              icon="i-lucide-history"
              :label="term"
              class="justify-start"
              @click="applyTerm(term)"
            />
            <UButton
              block
              size="sm"
              color="neutral"
              variant="ghost"
              icon="i-lucide-trash-2"
              label="최근 검색어 지우기"
              class="mt-1 justify-start"
              @click="cart.clearRecentSearches"
            />
          </div>
        </template>
      </UPopover>
      <UButton
        type="submit"
        color="primary"
        icon="i-lucide-search"
        label="검색"
      />
      <p
        v-if="activeQuery"
        class="w-full sk-meta"
      >
        "{{ activeQuery }}" 검색 결과 {{ filteredResults.length }}건
      </p>
    </form>

    <AfmCard
      icon="i-lucide-database"
      :title="activeQuery ? '검색 결과' : '최근 측정'"
      :count="filteredResults.length"
      flush
    >
      <template #actions>
        <UInput
          v-model="innerFilter"
          type="search"
          size="xs"
          icon="i-lucide-filter"
          placeholder="결과 내 필터"
          aria-label="결과 내 필터"
          class="w-48"
        />
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
      <ul
        v-else
        class="max-h-[640px] divide-y divide-(--sk-border-soft) overflow-y-auto"
      >
        <li
          v-for="result in filteredResults"
          :key="result.filename"
          class="flex items-center gap-3 px-4 py-3 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
        >
          <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
            <!-- Three identifiers, three forms: the date steps back so the
                 recipe is the row's headline, and lot / slot each carry the
                 eyebrow that names them. -->
            <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ result.formattedDate }}
            </span>
            <span class="text-sm font-semibold text-(--sk-ink)">
              {{ result.recipeName }}
            </span>
            <!-- One unit, so a narrow row wraps the tags together instead of
                 stranding the slot on a line of its own. -->
            <span class="flex items-center gap-x-3">
              <AfmLotSlotTags
                :lot-id="result.lotId"
                :slot-number="result.slotNumber"
              />
              <UBadge
                :label="result.measuredInfo"
                color="neutral"
                variant="outline"
              />
            </span>
          </div>

          <div class="flex shrink-0 items-center gap-1">
            <UIcon
              v-for="dt in DATA_TYPES.filter(dt => result[dt.key])"
              :key="dt.key"
              :name="dt.icon"
              class="size-3.5 text-(--sk-ink-muted)"
              :title="dt.tooltip"
            />
          </div>

          <UButton
            size="xs"
            color="neutral"
            :variant="cart.isInGroup(result.filename) ? 'subtle' : 'outline'"
            :icon="cart.isInGroup(result.filename) ? 'i-lucide-check' : 'i-lucide-plus'"
            :aria-label="cart.isInGroup(result.filename) ? '그룹에서 제거' : '그룹에 추가'"
            :aria-pressed="cart.isInGroup(result.filename)"
            class="shrink-0"
            @click="toggleGroup(result)"
          />
          <UButton
            size="xs"
            color="primary"
            icon="i-lucide-square-arrow-out-up-right"
            label="상세 보기"
            class="shrink-0"
            @click="$emit('view-details', result)"
          />
        </li>
      </ul>
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

const DATA_TYPES = [
  { key: 'hasProfile', icon: 'i-lucide-line-chart', tooltip: '프로파일 데이터' },
  { key: 'hasData', icon: 'i-lucide-database', tooltip: '측정 데이터' },
  { key: 'hasImage', icon: 'i-lucide-image', tooltip: '프로파일 이미지' },
  { key: 'hasAlign', icon: 'i-lucide-align-vertical-justify-center', tooltip: 'Align 이미지' },
  { key: 'hasTip', icon: 'i-lucide-pin', tooltip: 'Tip 이미지' }
] as const

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
</script>
