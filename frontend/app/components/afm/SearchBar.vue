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
      </div>

      <!-- Filters narrow the list, so every active one is terracotta. -->
      <div class="flex flex-wrap items-center gap-2 border-t border-(--sk-border-soft) pt-3">
        <USelectMenu
          v-model="recipes"
          multiple
          :items="recipeNames"
          :search-input="recipeNames.length > 8 ? { placeholder: 'Recipe 검색' } : false"
          :content="{ align: 'start' }"
          :ui="{ content: scopeMenuUi.content, itemTrailingIcon: 'hidden' }"
          aria-label="Recipe 필터"
          size="sm"
          color="neutral"
          variant="outline"
          trailing-icon="i-lucide-chevron-down"
          class="max-w-64"
          :class="recipes.length ? 'bg-(--sk-brand) text-(--sk-brand-fg) ring-(--sk-brand) hover:bg-(--sk-brand) [&_svg]:text-(--sk-brand-fg) [&_.sk-eyebrow]:text-(--sk-brand-fg)' : ''"
        >
          <template #default>
            <span class="sk-eyebrow">Recipe</span>
            <span class="truncate font-medium">{{ recipeLabel }}</span>
          </template>
          <template #item-leading="{ item }">
            <AppSelectCheck :checked="recipes.includes(item)" />
          </template>
          <template #item-trailing="{ item }">
            <span class="ml-auto pl-3 sk-value-num">{{ recipeCounts.get(item) }}</span>
          </template>
        </USelectMenu>

        <UInput
          v-model="lot"
          size="sm"
          autocomplete="off"
          placeholder="예: T7HQR"
          aria-label="Lot 필터"
          class="w-40"
          :class="lot.trim() ? '[&_.sk-eyebrow]:text-(--sk-brand-ink)' : ''"
          :ui="{ base: `ps-10 font-mono ${lot.trim() ? 'bg-(--sk-brand-soft) text-(--sk-brand-ink) ring-(--sk-brand)' : ''}` }"
        >
          <template #leading>
            <span class="sk-eyebrow">Lot</span>
          </template>
        </UInput>

        <span class="mx-1 h-5 w-px bg-(--sk-border)" />

        <span class="sk-eyebrow">기간</span>
        <div class="flex gap-1">
          <SkChip
            v-for="preset in PRESETS"
            :key="preset.label"
            size="sm"
            :label="preset.label"
            :active="days === preset.days"
            @click="days = preset.days"
          />
        </div>
        <span
          v-if="range"
          class="sk-value-num"
        >{{ range[0].slice(5) }} ~ {{ range[1].slice(5) }}</span>

        <UButton
          v-if="hasFilters"
          type="button"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-rotate-ccw"
          label="필터 초기화"
          @click="resetFilters"
        />
      </div>
    </form>

    <AfmCard
      icon="i-lucide-database"
      :title="activeQuery || hasFilters ? '검색 결과' : '최근 측정'"
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
      <template v-else>
        <div class="flex items-center gap-2.5 border-b border-(--sk-border-soft) bg-(--sk-muted-surface) px-4 py-2">
          <AfmGroupCheck
            :checked="allInGroup ? true : someInGroup ? 'indeterminate' : false"
            label="보이는 결과 모두 담기"
            :disabled="!groupRoom && !someInGroup"
            @toggle="toggleAll"
          />
          <span class="sk-meta">
            {{ allLabel }}
          </span>
          <span class="ml-auto sk-meta">
            체크하면 오른쪽 <b class="font-semibold text-(--sk-ink)">그룹</b>에 담깁니다
          </span>
        </div>
        <!-- One row per measurement, laid out as a table: fixed tracks keep
             the date, lot, slot and data columns aligned down the list, and
             only the recipe column flexes (and truncates). Its 11rem floor
             is what makes a narrow card scroll sideways rather than squeeze
             the recipe to nothing. -->
        <ul class="max-h-[620px] divide-y divide-(--sk-border-soft) overflow-auto">
          <li
            v-for="result in filteredResults"
            :key="result.filename"
            class="grid grid-cols-[auto_9.5rem_minmax(11rem,1fr)_6.5rem_4rem_5.5rem_3.5rem_auto] items-center gap-3 px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
            :class="cart.isInGroup(result.filename) ? 'bg-(--sk-muted-surface)' : ''"
          >
            <AfmGroupCheck
              :checked="cart.isInGroup(result.filename)"
              label="그룹에 담기"
              :disabled="!groupRoom && !cart.isInGroup(result.filename)"
              @toggle="cart.toggleGroup(result)"
            />

            <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ result.formattedDate }}
            </span>

            <span class="flex min-w-0 items-center gap-2">
              <span class="truncate text-sm font-semibold text-(--sk-ink)">
                {{ result.recipeName }}
              </span>
              <UBadge
                v-if="result.measuredInfo"
                :label="result.measuredInfo"
                color="neutral"
                variant="outline"
                class="shrink-0"
              />
            </span>

            <!-- Two roots, so Lot and Slot land in their own tracks. -->
            <AfmLotSlotTags
              :lot-id="result.lotId"
              :slot-number="result.slotNumber"
            />

            <span class="flex items-center gap-1">
              <UIcon
                v-for="dt in DATA_TYPES.filter(dt => result[dt.key])"
                :key="dt.key"
                :name="dt.icon"
                class="size-3.5 text-(--sk-ink-muted)"
                :title="dt.tooltip"
              />
            </span>

            <span
              v-if="viewed.has(result.filename)"
              class="flex items-center gap-1 sk-label"
            >
              <UIcon
                name="i-lucide-eye"
                class="size-3"
              />조회함
            </span>
            <span v-else />

            <UButton
              size="sm"
              color="neutral"
              variant="outline"
              trailing-icon="i-lucide-arrow-up-right"
              label="상세 보기"
              @click="$emit('view-details', result)"
            />
          </li>
        </ul>
      </template>
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
const rows = computed(() => files.value ?? [])

const query = ref('')
const activeQuery = ref('')
const innerFilter = ref('')
const recipes = ref<string[]>([])
const lot = ref('')
const days = ref<number | null>(null)

// 기간 counts back from today, in the viewer's own time zone.
const today = todayStamp()
const PRESETS = [
  { label: '전체', days: null },
  { label: '오늘', days: 1 },
  { label: '3일', days: 3 },
  { label: '7일', days: 7 }
]

// The box's native clear button empties it; an empty box is no search.
watch(query, (next) => {
  if (!next) activeQuery.value = ''
})

// Each recipe option carries how many measurements it has in the whole list.
const recipeCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const row of rows.value) counts.set(row.recipeName, (counts.get(row.recipeName) ?? 0) + 1)
  return counts
})
const recipeNames = computed(() => [...recipeCounts.value.keys()].sort())
const recipeLabel = computed(() =>
  recipes.value.length > 1 ? `${recipes.value.length}개 선택` : recipes.value[0] ?? '전체'
)

const range = computed(() => dateWindow(rows.value, days.value, today))
const hasFilters = computed(() => recipes.value.length > 0 || !!lot.value.trim() || days.value !== null)
const resetFilters = () => {
  recipes.value = []
  lot.value = ''
  days.value = null
}

const filteredResults = computed(() => filterMeasurements(rows.value, {
  terms: [activeQuery.value, innerFilter.value],
  recipes: recipes.value,
  lot: lot.value,
  days: days.value,
  today
}))

const viewed = computed(() => new Set(cart.viewHistory.value.map(item => item.filename)))

const someInGroup = computed(() => filteredResults.value.some(row => cart.isInGroup(row.filename)))
const allInGroup = computed(() => filteredResults.value.every(row => cart.isInGroup(row.filename)))
const groupRoom = cart.groupRoom
// A full group takes no more, so the box then empties the visible rows instead.
const toggleAll = () => {
  if (allInGroup.value || !groupRoom.value) cart.removeFromGroup(...filteredResults.value.map(row => row.filename))
  else cart.addToGroup(...filteredResults.value)
}
const allLabel = computed(() => {
  const count = filteredResults.value.length
  const missing = filteredResults.value.filter(row => !cart.isInGroup(row.filename)).length
  if (!missing) return `보이는 ${count}건 모두 담김`
  if (!groupRoom.value) return `그룹이 가득 찼습니다 · 최대 ${AFM_GROUP_MAX}건`
  if (missing > groupRoom.value) return `보이는 ${count}건 중 위에서부터 ${groupRoom.value}건만 담깁니다 · 그룹 최대 ${AFM_GROUP_MAX}건`
  return `보이는 ${count}건 모두 담기`
})

const DATA_TYPES = [
  { key: 'hasProfile', icon: 'i-lucide-line-chart', tooltip: '프로파일 데이터' },
  { key: 'hasData', icon: 'i-lucide-database', tooltip: '측정 데이터' },
  { key: 'hasImage', icon: 'i-lucide-image', tooltip: '프로파일 이미지' },
  { key: 'hasAlign', icon: 'i-lucide-align-vertical-justify-center', tooltip: 'Align 이미지' },
  { key: 'hasTip', icon: 'i-lucide-pin', tooltip: 'Tip 이미지' }
] as const

const commitSearch = () => {
  activeQuery.value = query.value.trim()
  cart.recordRecentSearch(activeQuery.value)
}

const applyTerm = (term: string) => {
  query.value = term
  activeQuery.value = term
}
</script>
