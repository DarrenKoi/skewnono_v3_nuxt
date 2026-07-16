<template>
  <dl class="flex flex-wrap items-center gap-x-3 gap-y-1">
    <div
      v-for="item in items"
      :key="item.label"
      class="inline-flex items-baseline gap-1 whitespace-nowrap"
    >
      <dt class="text-[10px] font-medium text-(--sk-ink-muted)">
        {{ item.label }}
      </dt>
      <dd
        class="font-mono text-[11px] font-semibold tabular-nums"
        :class="recipeStatusSummaryValueClass(item.tone)"
      >
        {{ item.value }}
      </dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
import {
  recipeStatusSummaryValueClass,
  type RecipeStatusSummaryItem
} from '~/utils/recipeStatusSummary'

defineProps<{
  items: readonly RecipeStatusSummaryItem[]
}>()
</script>
