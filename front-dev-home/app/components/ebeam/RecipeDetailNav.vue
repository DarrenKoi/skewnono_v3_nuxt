<script setup lang="ts">
import {
  buildRecipeDetailNavItems,
  type RecipeDetailScreen
} from '~/utils/recipeView'

const props = defineProps<{
  toolType: string
  fab: string
  recipeName: string
  activeScreen: RecipeDetailScreen
}>()

const route = useRoute()
const backRoute = computed(() => (
  `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`
))
const { goBack } = useHistoryBack(backRoute)
const items = computed(() => buildRecipeDetailNavItems(
  props.toolType,
  props.fab,
  props.recipeName,
  props.activeScreen,
  route.query.set
))
</script>

<template>
  <nav
    aria-label="Recipe 상세 화면 이동"
    class="flex flex-wrap items-center gap-2"
  >
    <UButton
      size="md"
      color="neutral"
      variant="outline"
      icon="i-lucide-arrow-left"
      label="돌아가기"
      class="rounded-full font-semibold"
      :to="backRoute"
      @click.prevent="goBack"
    />
    <div class="inline-flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60">
      <UButton
        v-for="item in items"
        :key="item.screen"
        size="sm"
        color="neutral"
        :variant="item.active ? 'solid' : 'ghost'"
        :icon="item.icon"
        :label="item.label"
        :to="item.to"
        :aria-current="item.active ? 'page' : undefined"
        class="font-semibold"
        @click="item.active && $event.preventDefault()"
      />
    </div>
  </nav>
</template>
