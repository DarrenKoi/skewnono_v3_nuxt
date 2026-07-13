<template>
  <div class="flex items-center gap-2">
    <UTooltip
      v-for="action in RECIPE_ROW_ACTIONS"
      :key="action.screen"
      :text="action.label"
    >
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        class="-my-1"
        :icon="action.icon"
        :aria-label="`${recipeName} ${action.label}`"
        @click="open(action.screen)"
      />
    </UTooltip>
  </div>
</template>

<script setup lang="ts">
import {
  RECIPE_ROW_ACTIONS,
  recipeDetailRoute,
  type RecipeDetailScreen
} from '~/utils/recipeView'

// Compact icon-only variant of the recipe-search row buttons, for dense
// ranking tables (recipe-tat, fail-issue). The detail screens' "돌아가기"
// button history-backs to whichever table launched them.
const props = defineProps<{
  toolType: string
  fab: string
  recipeName: string
}>()

const router = useRouter()

const open = (screen: RecipeDetailScreen) => {
  router.push(recipeDetailRoute(props.toolType, props.fab, screen, props.recipeName))
}
</script>
