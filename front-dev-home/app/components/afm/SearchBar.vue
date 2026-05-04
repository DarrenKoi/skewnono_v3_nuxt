<template>
  <div class="space-y-4">
    <section class="dashboard-surface rounded-2xl p-5">
      <form
        class="group flex h-12 w-full items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 shadow-sm transition focus-within:border-zinc-300 focus-within:ring-4 focus-within:ring-zinc-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:focus-within:border-zinc-700 dark:focus-within:ring-zinc-800/70"
        @submit.prevent="commitSearch"
      >
        <UIcon
          name="i-lucide-search"
          class="h-5 w-5 shrink-0 text-zinc-400"
        />
        <input
          v-model="query"
          type="search"
          inputmode="search"
          autocomplete="off"
          placeholder="Search by Lot ID, Recipe, Date (e.g. CMP, T7HQR42TA, 250609)"
          class="min-w-0 flex-1 bg-transparent text-sm text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50"
          aria-label="Search AFM measurements"
        >
        <UButton
          v-if="query"
          type="button"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="Clear search"
          class="rounded-full"
          @click="clearQuery"
        />
        <UPopover v-if="recentTerms.length > 0">
          <UButton
            type="button"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-history"
            aria-label="Recent searches"
            class="rounded-full"
          />
          <template #content>
            <div class="w-64 p-2">
              <p class="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Recent searches
              </p>
              <button
                v-for="term in recentTerms"
                :key="term"
                type="button"
                class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800"
                @click="useRecentTerm(term)"
              >
                <UIcon name="i-lucide-history" class="h-4 w-4 text-zinc-400" />
                <span class="truncate">{{ term }}</span>
              </button>
              <button
                type="button"
                class="mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30"
                @click="clearRecentTerms"
              >
                <UIcon name="i-lucide-trash-2" class="h-4 w-4" />
                Clear recent
              </button>
            </div>
          </template>
        </UPopover>
        <UButton
          type="submit"
          size="xs"
          color="neutral"
          variant="solid"
          icon="i-lucide-arrow-right"
          aria-label="Search"
          class="rounded-full"
        />
      </form>

      <p
        v-if="activeQuery && filteredResults.length === 0"
        class="mt-3 text-center text-xs text-zinc-500"
      >
        No results found for "{{ activeQuery }}"
      </p>
      <p
        v-else-if="activeQuery"
        class="mt-3 text-center text-xs text-zinc-500"
      >
        Found {{ filteredResults.length }} results for "{{ activeQuery }}"
      </p>
    </section>

    <section class="dashboard-surface rounded-2xl">
      <header class="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-3 dark:border-zinc-800">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-database" class="h-4 w-4 text-zinc-500" />
          <h2 class="text-sm font-semibold">
            {{ activeQuery ? 'Search Results' : 'Recent Measurements' }}
          </h2>
          <span class="text-xs text-zinc-500 tabular-nums">
            ({{ filteredResults.length }}{{ filteredResults.length !== mockResults.length ? `/${mockResults.length}` : '' }})
          </span>
        </div>
        <div class="relative w-48">
          <UIcon
            name="i-lucide-filter"
            class="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400"
          />
          <input
            v-model="innerFilter"
            type="search"
            placeholder="Filter results..."
            class="h-8 w-full rounded-md border border-zinc-200 bg-white pl-7 pr-2 text-xs outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
            aria-label="Filter results"
          >
        </div>
      </header>

      <div
        v-if="filteredResults.length === 0"
        class="px-5 py-10 text-center text-sm text-zinc-500"
      >
        No measurements to show
      </div>

      <ul
        v-else
        class="max-h-[640px] divide-y divide-zinc-200 overflow-y-auto dark:divide-zinc-800"
      >
        <li
          v-for="result in filteredResults"
          :key="result.filename"
          class="flex items-start gap-3 px-5 py-3"
        >
          <div class="min-w-0 flex-1 space-y-1">
            <p class="text-sm font-semibold tabular-nums">
              {{ result.formattedDate }}
            </p>
            <p class="text-sm text-zinc-700 dark:text-zinc-300">
              {{ result.recipeName }}
            </p>
            <p class="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
              <span class="font-mono">{{ result.lotId }}</span>
              <UBadge
                v-if="isInGroup(result.filename)"
                label="GROUPED"
                color="success"
                size="xs"
                variant="subtle"
              />
            </p>
            <div class="flex flex-wrap gap-1.5 pt-1">
              <UBadge
                :label="`Slot ${result.slotNumber}`"
                color="primary"
                size="xs"
                variant="outline"
              />
              <UBadge
                :label="result.measuredInfo"
                color="neutral"
                size="xs"
                variant="outline"
              />
              <UIcon
                v-for="dt in availableDataTypes(result)"
                :key="dt.key"
                :name="dt.icon"
                class="h-4 w-4 text-emerald-500"
                :title="dt.tooltip"
              />
            </div>
          </div>
          <div class="flex shrink-0 flex-col gap-1.5">
            <UButton
              size="xs"
              color="success"
              variant="outline"
              icon="i-lucide-plus"
              :disabled="isInGroup(result.filename)"
              @click="$emit('add-to-group', result)"
            >
              Add to Group
            </UButton>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              @click="$emit('view-details', result)"
            >
              View Details
            </UButton>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AfmMeasurement } from '~/composables/useAfmCart'

const props = defineProps<{
  toolId: string
  isInGroup: (filename: string) => boolean
}>()

defineEmits<{
  (event: 'add-to-group' | 'view-details', measurement: AfmMeasurement): void
}>()

const { recentSearches: recentTerms, recordRecentSearch, clearRecentSearches } = useAfmCart(props.toolId)

const query = ref('')
const activeQuery = ref('')
const innerFilter = ref('')

const mockResults = computed<AfmMeasurement[]>(() => {
  const recipes = ['CMP_PRE', 'CMP_POST', 'ETCH_GATE', 'ETCH_VIA', 'DEP_OXIDE', 'DEP_NITRIDE']
  const lots = ['T7HQR42TA', 'T7HQR43TB', 'T7HQR44TC', 'T7HQR45TD', 'T7HQR46TE']
  const measured = ['CD', 'Step Height', 'Roughness', 'Profile', 'Sidewall']
  return Array.from({ length: 12 }, (_, i) => ({
    filename: `${props.toolId}_${i.toString().padStart(3, '0')}.afm`,
    recipeName: recipes[i % recipes.length] ?? 'CMP_PRE',
    lotId: lots[i % lots.length] ?? 'T7HQR42TA',
    slotNumber: (i % 25) + 1,
    measuredInfo: measured[i % measured.length] ?? 'CD',
    formattedDate: `2026-04-${(i % 28 + 1).toString().padStart(2, '0')}`,
    hasProfile: i % 2 === 0,
    hasData: true,
    hasImage: i % 3 !== 0,
    hasAlign: i % 4 === 0,
    hasTip: i % 5 === 0
  }))
})

const matchesTerm = (row: AfmMeasurement, term: string) => {
  return [
    row.filename,
    row.recipeName,
    row.lotId,
    row.formattedDate,
    String(row.slotNumber),
    row.measuredInfo
  ].some(value => value.toLowerCase().includes(term))
}

const filteredResults = computed(() => {
  const search = activeQuery.value.toLowerCase().trim()
  const filter = innerFilter.value.toLowerCase().trim()
  return mockResults.value.filter((row) => {
    if (search && !matchesTerm(row, search)) return false
    if (filter && !matchesTerm(row, filter)) return false
    return true
  })
})

const dataTypeMap = [
  { key: 'hasProfile', icon: 'i-lucide-line-chart', tooltip: 'Profile data' },
  { key: 'hasData', icon: 'i-lucide-database', tooltip: 'Measurement data' },
  { key: 'hasImage', icon: 'i-lucide-image', tooltip: 'Profile image' },
  { key: 'hasAlign', icon: 'i-lucide-align-vertical-justify-center', tooltip: 'Alignment' },
  { key: 'hasTip', icon: 'i-lucide-pin', tooltip: 'Tip image' }
] as const

const availableDataTypes = (row: AfmMeasurement) =>
  dataTypeMap.filter(dt => Boolean(row[dt.key]))

const commitSearch = () => {
  const trimmed = query.value.trim()
  activeQuery.value = trimmed
  recordRecentSearch(trimmed)
}

const clearQuery = () => {
  query.value = ''
  activeQuery.value = ''
}

const useRecentTerm = (term: string) => {
  query.value = term
  activeQuery.value = term
}

const clearRecentTerms = () => {
  clearRecentSearches()
}
</script>
