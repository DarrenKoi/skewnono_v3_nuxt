<template>
  <div class="flex items-center gap-2">
    <template
      v-for="action in RECIPE_ROW_ACTIONS"
      :key="action.screen"
    >
      <UDropdownMenu
        v-if="multiFab"
        :items="itemsFor(action.screen)"
      >
        <UTooltip :text="`${action.label} — FAB 선택`">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-my-1"
            :icon="action.icon"
            :aria-label="`${recipeName} ${action.label}`"
          />
        </UTooltip>
      </UDropdownMenu>
      <UTooltip
        v-else
        :text="action.label"
      >
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          class="-my-1"
          :icon="action.icon"
          :aria-label="`${recipeName} ${action.label}`"
          @click="open(action.screen, fabNames[0] ?? '')"
        />
      </UTooltip>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  RECIPE_ROW_ACTIONS,
  recipeDetailRoute,
  type RecipeDetailScreen
} from '~/utils/recipeView'

// Compact icon-only variant of the recipe-search row buttons, for dense
// ranking tables (recipe-tat, fail-issue). Ranking rows aggregate across the
// selected fabs, so when more than one fab contributed the action opens a
// per-fab picker — the detail registries are per-fab.
const props = defineProps<{
  toolType: string
  fabSegment: string
  fabNames: string[]
  recipeName: string
}>()

const router = useRouter()
const multiFab = computed(() => props.fabNames.length > 1)

const open = (screen: RecipeDetailScreen, ownerFab: string) => {
  router.push(recipeDetailRoute(
    props.toolType, props.fabSegment, screen, props.recipeName, 'redis', ownerFab
  ))
}

const itemsFor = (screen: RecipeDetailScreen) =>
  props.fabNames.map(fab => ({ label: fab, onSelect: () => open(screen, fab) }))
</script>
