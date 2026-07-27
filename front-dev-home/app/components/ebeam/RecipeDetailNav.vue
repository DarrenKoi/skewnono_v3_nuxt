<script setup lang="ts">
import {
  buildRecipeDetailNavItems,
  readRecipeSourceQuery,
  type RecipeDetailScreen
} from '~/utils/recipeView'

const props = defineProps<{
  toolType: string
  fab: string
  recipeName: string
  activeScreen: RecipeDetailScreen
  // Optional secondary line under the recipe name (e.g. timestamp).
  subtitle?: string
}>()

const route = useRoute()
const source = computed(() => readRecipeSourceQuery(route))
// Always route straight back to the recipe-search list — never rely on
// browser history, which may have landed the user here from elsewhere.
const backRoute = computed(() => (
  `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`
))
const items = computed(() => buildRecipeDetailNavItems(
  props.toolType,
  props.fab,
  props.recipeName,
  props.activeScreen,
  route.query.set,
  source.value
))
</script>

<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--sk-r-card)] p-1.5">
    <nav
      aria-label="Recipe 상세 화면 이동"
      class="flex flex-wrap items-center gap-2"
    >
      <UButton
        size="md"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="Recipe 검색으로"
        class="rounded-full font-semibold"
        :to="backRoute"
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

    <!-- Recipe identity lives on the right, mirroring the stats cluster in the
         장비 상태 / Recipe 현황 meta bars. -->
    <div class="ml-auto min-w-0 pr-1 text-right">
      <p class="sk-eyebrow text-(--sk-brand)">
        RECIPE
      </p>
      <p
        class="truncate font-mono text-[15px] font-bold leading-tight text-zinc-900 dark:text-zinc-100"
        :title="recipeName"
      >
        {{ recipeName || '—' }}
      </p>
      <p
        v-if="subtitle"
        class="mt-0.5 font-mono text-[11px] text-(--sk-ink-muted)"
      >
        {{ subtitle }}
      </p>
    </div>
  </div>
</template>
