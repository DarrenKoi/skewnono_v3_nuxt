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
      :key="recipePairKey(entry.fab_name, entry.name)"
      size="sm"
      :label="shortId(entry.name)"
      :aria-label="entry.name"
      :title="entry.name"
      :active="isActive(entry)"
      @click="switchTo(entry)"
    />
  </nav>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { readRecipeNameQuery, recipeDetailRoute, type RecipeDetailScreen } from '~/utils/recipeView'
import type { RecipeSelectionEntry } from '~/utils/recipeSelection'
import { recipePairKey } from '~/utils/recipePair'

const props = defineProps<{
  toolType: RecipeSearchToolType
  fabSegment: string
  ownerFab: string
  activeScreen: RecipeDetailScreen
}>()

const route = useRoute()
const router = useRouter()
const { entries } = useRecipeSelectionSet(props.toolType)

const availableEntries = computed(() =>
  props.activeScreen === 'open'
    ? entries.value.filter(entry => entry.source === 'redis')
    : entries.value
)

// Only show when the user arrived from the tray (set=1) with 2+ recipes.
// Otherwise render nothing so single-recipe (row-button) entry is unchanged.
const show = computed(() => Boolean(route.query.set) && availableEntries.value.length >= 2)

const activeName = computed(() => readRecipeNameQuery(route))

// Selection identity is (name, fab) — matching on name alone would mark two
// entries active at once when the same recipe name is selected from two fabs.
const isActive = (entry: RecipeSelectionEntry) =>
  entry.name === activeName.value && entry.fab_name === props.ownerFab

const shortId = (id: string) => (id.length > 28 ? `…${id.slice(-26)}` : id)

const switchTo = (entry: RecipeSelectionEntry) => {
  if (isActive(entry)) return
  // replace (not push) so the back button returns to the list, not each tab.
  // Route through recipeDetailRoute so the entry's OWN fab becomes the owner
  // fab query — switching to an entry selected from a different fab must not
  // keep fetching the previous owner's data. The URL's [fab] segment (which
  // may be a multi-fab sidebar selection) is untouched.
  const target = recipeDetailRoute(
    props.toolType,
    props.fabSegment,
    props.activeScreen,
    entry.name,
    entry.source,
    entry.fab_name
  )
  router.replace({
    path: target.path,
    query: { ...target.query, ...(route.query.set ? { set: route.query.set } : {}) }
  })
}
</script>
