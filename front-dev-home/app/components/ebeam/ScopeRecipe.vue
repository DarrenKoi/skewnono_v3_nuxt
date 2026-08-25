<template>
  <!-- The recipe half of 비교 대상; the parameter lives in EbeamAnalysisBar
       below, where its list can exist. -->
  <div class="min-w-0">
    <p class="mb-1.5 sk-label">
      RECIPE
    </p>
    <!-- Searchable, not a plain <select>: even the measured-only list runs to
         hundreds of names, and search is how a known one is reached. The list
         is filtered and capped, and the caption says when it capped. -->
    <USelectMenu
      v-model:search-term="term"
      :model-value="recipeId ?? ALL_RECIPES"
      ignore-filter
      :items="items"
      :search-input="{ placeholder: 'recipe 이름 검색 — 비우면 전체' }"
      :loading="recipesPending"
      icon="i-lucide-search"
      color="neutral"
      variant="outline"
      class="w-full"
      :ui="scopeMenuUi"
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
      <template v-if="overflowed">
        {{ matched.length.toLocaleString() }}건 중 {{ RECIPE_LIMIT }}건만 표시합니다 — 더 좁혀서 검색하십시오.
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
import { useMenuFilter } from '~/composables/useMenuFilter'
import { scopeMenuUi } from '~/utils/scopeMenuUi'

const ALL_RECIPES = '전체 (서버 기본)'
// The measured-recipe list is hundreds of names, not the catalogue's ~50,000,
// but the cap stays: it costs nothing and the caption says when it bound.
const RECIPE_LIMIT = 100

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

const { term, matched, overflowed, items } = useMenuFilter(
  () => props.recipeNames,
  { sentinel: ALL_RECIPES, limit: RECIPE_LIMIT }
)
</script>
