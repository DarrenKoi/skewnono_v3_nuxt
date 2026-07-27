<template>
  <nav
    v-if="show"
    aria-label="작업 세트 recipe 전환"
    class="flex flex-wrap items-center gap-1.5"
  >
    <span class="px-1 sk-eyebrow text-(--sk-brand)">
      작업 세트 · {{ availableEntries.length }}
    </span>
    <SkNavPill
      v-for="entry in availableEntries"
      :key="entry.name"
      size="sm"
      :label="shortId(entry.name)"
      :aria-label="entry.name"
      :title="entry.name"
      :active="entry.name === activeName"
      @click="switchTo(entry)"
    />
  </nav>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { readRecipeNameQuery, type RecipeDetailScreen } from '~/utils/recipeView'
import type { RecipeSelectionEntry } from '~/utils/recipeSelection'

const props = defineProps<{
  toolType: RecipeSearchToolType
  fab: string
  activeScreen: RecipeDetailScreen
}>()

const route = useRoute()
const router = useRouter()
const { entries } = useRecipeSelectionSet(props.toolType, props.fab)

const availableEntries = computed(() =>
  props.activeScreen === 'open'
    ? entries.value.filter(entry => entry.source === 'redis')
    : entries.value
)

// Only show when the user arrived from the tray (set=1) with 2+ recipes.
// Otherwise render nothing so single-recipe (row-button) entry is unchanged.
const show = computed(() => Boolean(route.query.set) && availableEntries.value.length >= 2)

const activeName = computed(() => readRecipeNameQuery(route))

const shortId = (id: string) => (id.length > 28 ? `…${id.slice(-26)}` : id)

const switchTo = (entry: RecipeSelectionEntry) => {
  if (entry.name === activeName.value) return
  // replace (not push) so the back button returns to the list, not each tab.
  // Preserve the existing query (keeps the set=1 flag), but derive source
  // solely from the selected entry so a Redis route stays source-less.
  const nextQuery = { ...route.query }
  delete nextQuery.source
  nextQuery.recipe_name = entry.name
  if (entry.source === 'opensearch') nextQuery.source = 'opensearch'
  router.replace({ query: nextQuery })
}
</script>
