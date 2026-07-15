<template>
  <nav
    v-if="show"
    aria-label="작업 세트 recipe 전환"
    class="flex flex-wrap items-center gap-1.5"
  >
    <span class="px-1 sk-eyebrow text-(--sk-brand)">
      작업 세트 · {{ selected.length }}
    </span>
    <SkNavPill
      v-for="name in selected"
      :key="name"
      size="sm"
      :label="shortId(name)"
      :aria-label="name"
      :title="name"
      :active="name === activeName"
      @click="switchTo(name)"
    />
  </nav>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { readRecipeNameQuery } from '~/utils/recipeView'

const props = defineProps<{
  toolType: RecipeSearchToolType
  fab: string
}>()

const route = useRoute()
const router = useRouter()
const { selected } = useRecipeSelectionSet(props.toolType, props.fab)

// Only show when the user arrived from the tray (set=1) with 2+ recipes.
// Otherwise render nothing so single-recipe (row-button) entry is unchanged.
const show = computed(() => Boolean(route.query.set) && selected.value.length >= 2)

const activeName = computed(() => readRecipeNameQuery(route))

const shortId = (id: string) => (id.length > 28 ? `…${id.slice(-26)}` : id)

const switchTo = (name: string) => {
  if (name === activeName.value) return
  // replace (not push) so the back button returns to the list, not each tab.
  // Preserve the existing query (keeps the set=1 flag).
  router.replace({ query: { ...route.query, recipe_name: name } })
}
</script>
