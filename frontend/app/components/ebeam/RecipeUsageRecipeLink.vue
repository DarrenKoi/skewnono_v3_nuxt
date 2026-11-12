<template>
  <button
    type="button"
    class="font-mono font-semibold text-(--sk-ink) underline decoration-(--sk-border) underline-offset-2 hover:decoration-(--sk-ink) focus-visible:decoration-(--sk-ink)"
    :title="`${recipeId} 사용 이력 보기`"
    @click="selectRecipe(recipeId)"
  >
    {{ recipeId }}
  </button>
</template>

<script setup lang="ts">
// A recipe_id in a table cell that opens EbeamRecipeUsageDetail for it.
defineProps<{ recipeId: string }>()

const { selectRecipe } = useRecipeUsageSelection()
</script>
