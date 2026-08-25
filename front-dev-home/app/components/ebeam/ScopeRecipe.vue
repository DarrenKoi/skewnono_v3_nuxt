<template>
  <!-- The recipe half of 비교 대상. The parameter used to sit beside it as the
       second step of one choice; it now lives in the 분석 조건 bar below, because
       its list is read from the measurement data this pick selects — there is
       nothing to list until this has been answered. -->
  <div class="min-w-0">
    <p class="mb-1.5 sk-label">
      RECIPE
    </p>
    <!-- Searchable, not a plain <select>: even the measured-only list runs to
           hundreds of names, and search is how a known one is reached. The list
           is filtered and capped, and the caption says when it capped. -->
    <USelectMenu
      v-model:search-term="recipeTerm"
      :model-value="recipeId ?? ALL_RECIPES"
      ignore-filter
      :items="recipeItems"
      :search-input="{ placeholder: 'recipe 이름 검색 — 비우면 전체' }"
      :loading="recipesPending"
      icon="i-lucide-search"
      color="neutral"
      variant="outline"
      class="w-full"
      :ui="POPPER_UI"
      @update:model-value="onRecipe($event === ALL_RECIPES ? '' : String($event))"
    >
      <!-- The trigger is one cell of the scope bar, so the name is clipped
             here and carried in full by the title and by the caption below. -->
      <template #default>
        <span
          class="truncate font-mono text-[13px]"
          :title="recipeId ?? ALL_RECIPES"
        >{{ recipeId ?? ALL_RECIPES }}</span>
      </template>

      <!-- `tools == 1` means one tool ran it, so no PAIR exists and no direct
             skew can ever come out of it however many runs it has. Marked rather
             than hidden: it is still a legitimate thing to look at, and the list
             is already ordered so these sink to the bottom. -->
      <template #item-trailing="{ item }">
        <span
          v-if="recipesWithoutAPair.has(String(item))"
          class="ml-auto sk-signal-badge bg-(--sk-warn-soft) text-(--sk-warn)"
          title="이 recipe 를 측정한 장비가 1대뿐이라 장비쌍이 없습니다"
        >장비 1대</span>
      </template>
    </USelectMenu>
    <p class="mt-1.5 sk-field-label leading-relaxed">
      <template v-if="recipesOverflowed">
        {{ recipeMatchCount.toLocaleString() }}건 중 {{ RECIPE_LIMIT }}건만 표시합니다 — 더 좁혀서 검색하십시오.
      </template>
      <template v-else-if="recipeId">
        <!-- `break-all`, not truncate: this is the one place the whole name is
               readable without opening the menu, and a class/recipe full name has
               no spaces to wrap at. -->
        <!-- Full ink: this is the recipe ID itself, the value the caption exists
               to make readable. DESIGN.md §Text — muted ink is "never data
               values", and the litmus is "value → ink; label → ink-muted". -->
        <span class="font-mono break-all text-(--sk-ink)">{{ recipeId }}</span>
      </template>
      <template v-else>
        {{ recipeNames.length.toLocaleString() }}건 측정됨 · recipe 를 골라야 결과가 계산됩니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { filterByTerm } from '~/utils/hardwareCompare'

// Sentinels for "no filter". A plain '' cannot be a USelectMenu item, and null
// would render as an empty row rather than as a readable choice.
const ALL_RECIPES = '전체 (서버 기본)'
// The measured-recipe list is hundreds of names, not the catalogue's ~50,000,
// but the cap stays: it costs nothing and the caption says when it bound.
const RECIPE_LIMIT = 100

// NuxtUI pins the dropdown to the trigger (`w-(--reka-select-trigger-width)` in
// .nuxt/ui/select-menu.ts), and the trigger is one cell of the scope bar — about
// half of the bar's free width, and narrower still once the bar wraps. A
// class/recipe full name such as CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5
// does not fit in that, and two recipes differing only in their suffix become
// indistinguishable in the list you pick from. So the POPPER widens instead of
// the cell: it floats over the results below, where the space already exists.
// Bounded by the viewport so a narrow window cannot push it off-screen.
const POPPER_UI = {
  content: 'w-auto min-w-full max-w-[min(48rem,calc(100vw-2rem))]',
  item: 'font-mono text-[13px]'
}

const props = withDefaults(defineProps<{
  recipeId: string | null
  recipeNames: string[]
  recipesPending: boolean
  /** Recipes only ONE tool measured — they cannot yield a pair. */
  recipesWithoutAPair?: Set<string>
}>(), {
  recipesWithoutAPair: () => new Set<string>()
})

const emit = defineEmits<{
  (e: 'update:recipeId', value: string | null): void
}>()

const onRecipe = (value: string) => emit('update:recipeId', value || null)

const recipeTerm = ref('')
const recipeMatched = computed(() => filterByTerm(props.recipeNames, recipeTerm.value, name => name))
const recipeMatchCount = computed(() => recipeMatched.value.length)
const recipesOverflowed = computed(() => recipeMatchCount.value > RECIPE_LIMIT)
// The sentinel stays at the top so clearing the filter is always one click away,
// even when the search box is narrowing the list down to a hundred.
const recipeItems = computed(() => [ALL_RECIPES, ...recipeMatched.value.slice(0, RECIPE_LIMIT)])
</script>
