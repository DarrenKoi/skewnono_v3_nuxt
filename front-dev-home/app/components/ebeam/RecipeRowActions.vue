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
  recipeDetailId,
  recipeDetailRoute,
  type RecipeDetailScreen
} from '~/utils/recipeView'

// Compact icon-only variant of the recipe-search row buttons, for dense
// ranking tables (recipe-tat, fail-issue). Ranking rows aggregate across the
// selected fabs, so when more than one fab contributed the action opens a
// per-fab picker — the detail registries are per-fab.
//
// BOTH names are taken, and they are not interchangeable: a ranking row shows
// the bare `recipe_name` (its class already has a column of its own) while the
// detail screens are addressed by the class-qualified `full_name`. Resolving
// that here rather than at the three call sites is deliberate — passing the
// wrong one is silent at home and a 502 at the office, so the rule belongs in
// one place. See `recipeDetailId`.
const props = defineProps<{
  toolType: string
  fabSegment: string
  fabNames: string[]
  recipeName: string
  fullName?: string
}>()

const router = useRouter()
const multiFab = computed(() => props.fabNames.length > 1)
const detailId = computed(() => recipeDetailId({
  recipe_name: props.recipeName,
  full_name: props.fullName
}))

const open = (screen: RecipeDetailScreen, ownerFab: string) => {
  router.push(recipeDetailRoute(
    props.toolType, props.fabSegment, screen, detailId.value, 'redis', ownerFab
  ))
}

const itemsFor = (screen: RecipeDetailScreen) =>
  props.fabNames.map(fab => ({ label: fab, onSelect: () => open(screen, fab) }))
</script>
