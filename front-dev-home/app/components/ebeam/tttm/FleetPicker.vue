<template>
  <div class="dashboard-surface rounded-2xl p-4 space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-(--sk-ink-subtle)">
        비교할 장비와 recipe · 이 설정은 이 브라우저에 저장됩니다
      </p>
      <button
        v-if="isCustomised"
        type="button"
        class="text-[11px] text-(--sk-ink-muted) underline underline-offset-2"
        @click="reset"
      >
        기본값으로
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span class="text-[11px] w-12 shrink-0 text-(--sk-ink-subtle)">장비</span>
      <button
        v-for="tool in tools"
        :key="tool.eqp_id"
        type="button"
        class="rounded-(--sk-r-chip) border px-2 py-0.5 text-xs transition-colors"
        :style="chipStyle(tool.eqp_id)"
        :aria-pressed="isSelected(tool.eqp_id)"
        @click="toggle(tool.eqp_id)"
      >
        {{ tool.label }}
      </button>
      <span
        v-if="selected.length < 2"
        class="text-[11px] text-(--sk-bad)"
      >비교하려면 2대 이상이어야 합니다.</span>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span class="text-[11px] w-12 shrink-0 text-(--sk-ink-subtle)">recipe</span>
      <!-- Searchable, not a plain <select>: R3 alone answers with 50,000 recipe
           names, and rendering that many <option> nodes locks the page. Search
           is the only way to reach one, so the list is filtered and capped. -->
      <USelectMenu
        v-model:search-term="searchTerm"
        :model-value="recipeId ?? ALL_RECIPES"
        ignore-filter
        :items="recipeItems"
        :search-input="{ placeholder: 'recipe 이름 검색…' }"
        :loading="recipesPending"
        size="xs"
        class="min-w-[20rem] flex-1"
        @update:model-value="onRecipe($event === ALL_RECIPES ? '' : String($event))"
      />
      <span class="text-[11px] text-(--sk-ink-subtle)">
        <template v-if="overflowed">
          {{ matchCount.toLocaleString() }}건 중 {{ RECIPE_LIMIT }}건만 표시합니다 — 더 좁혀서 검색하십시오.
        </template>
        <template v-else>
          recipe 를 고르면 그 recipe 만으로 다시 계산합니다.
        </template>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { filterByTerm } from '~/utils/hardwareCompare'
import type { ToolRef } from '~/composables/useTttmApi'

// Sentinel for "no recipe filter". A plain '' cannot be a USelectMenu item, and
// null would render as an empty row rather than as a readable choice.
const ALL_RECIPES = '전체 (서버 기본)'
// The catalogue is ~50,000 names per fab; this many rows is already more than
// anyone scrolls, and the caption says how many matched so the cap never hides
// the fact that it capped.
const RECIPE_LIMIT = 100

const props = defineProps<{
  tools: ToolRef[]
  /** Resolved ids actually in play — empty stored selection already expanded. */
  selected: string[]
  recipeId: string | null
  recipeNames: string[]
  recipesPending: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: string[]): void
  (e: 'update:recipeId', value: string | null): void
}>()

const isSelected = (eqp: string) => props.selected.includes(eqp)

// "Everything selected" is stored as an empty list, so a tool added to the fleet
// later shows up instead of being excluded by a selection saved before it
// existed. See resolveSelection in utils/tttmFleetSubset.
const isCustomised = computed(() => props.selected.length !== props.tools.length)

const normalise = (next: string[]) =>
  next.length === props.tools.length ? [] : next

const toggle = (eqp: string) => {
  const next = isSelected(eqp)
    ? props.selected.filter(id => id !== eqp)
    // Re-derive from the fleet order so the stored list never depends on the
    // order the user happened to click in.
    : props.tools.map(t => t.eqp_id).filter(id => id === eqp || isSelected(id))

  // A one-tool comparison is not a comparison; refuse the last removal the way
  // utils/fab.ts refuses to drop the last fab.
  if (next.length < 2) return
  emit('update:selected', normalise(next))
}

const reset = () => {
  emit('update:selected', [])
  emit('update:recipeId', null)
}

const onRecipe = (value: string) => emit('update:recipeId', value || null)

const searchTerm = ref('')
const matched = computed(() => filterByTerm(props.recipeNames, searchTerm.value, name => name))
const matchCount = computed(() => matched.value.length)
const overflowed = computed(() => matchCount.value > RECIPE_LIMIT)
// The sentinel stays at the top so clearing the filter is always one click away,
// even when the search box is narrowing 50,000 names down to a hundred.
const recipeItems = computed(() => [ALL_RECIPES, ...matched.value.slice(0, RECIPE_LIMIT)])

const chipStyle = (eqp: string) => isSelected(eqp)
  ? { background: 'var(--sk-accent-soft)', borderColor: 'var(--sk-accent-border)', color: 'var(--sk-ink)' }
  : { background: 'transparent', borderColor: 'var(--sk-border)', color: 'var(--sk-ink-subtle)' }
</script>
