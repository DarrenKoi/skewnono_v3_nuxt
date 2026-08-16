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

    <div class="space-y-2">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[11px] w-16 shrink-0 text-(--sk-ink-subtle)">장비</span>
        <span class="text-[11px] text-(--sk-ink-muted)">
          {{ tools.length }}대 중 {{ selected.length }}대 선택
        </span>
        <button
          type="button"
          class="text-[11px] text-(--sk-ink-muted) underline underline-offset-2 disabled:opacity-40 disabled:no-underline"
          :disabled="selected.length === tools.length"
          @click="selectAll"
        >
          전체 선택
        </button>
        <span
          v-if="selected.length < 2"
          class="text-[11px] text-(--sk-bad)"
        >비교하려면 2대 이상이어야 합니다.</span>
      </div>

      <!-- One row per model code. A fab carries up to ~18 CD-SEMs and the
           selection people want is usually a whole series, so the series
           label is itself the toggle for its tools. -->
      <div
        v-for="group in groups"
        :key="group.model"
        class="flex flex-wrap items-center gap-2"
      >
        <button
          type="button"
          class="w-16 shrink-0 text-left text-[11px] transition-colors"
          :class="isWholeGroupSelected(group) ? 'text-(--sk-ink)' : 'text-(--sk-ink-subtle)'"
          :aria-pressed="isWholeGroupSelected(group)"
          :title="`${group.model} ${group.tools.length}대 ${isWholeGroupSelected(group) ? '해제' : '선택'}`"
          @click="toggleGroup(group)"
        >
          {{ group.model }}
        </button>
        <button
          v-for="tool in group.tools"
          :key="tool.eqp_id"
          type="button"
          class="rounded-(--sk-r-chip) border px-2 py-0.5 text-xs transition-colors"
          :style="chipStyle(tool.eqp_id)"
          :aria-pressed="isSelected(tool.eqp_id)"
          @click="toggle(tool.eqp_id)"
        >
          {{ tool.label }}
        </button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span class="text-[11px] w-16 shrink-0 text-(--sk-ink-subtle)">recipe</span>
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
import { groupToolsByModel, orderSelection, type ToolGroup } from '~/utils/tttmToolGroups'
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

const fleetIds = computed(() => props.tools.map(t => t.eqp_id))
const groups = computed(() => groupToolsByModel(props.tools))

const isSelected = (eqp: string) => props.selected.includes(eqp)
const isWholeGroupSelected = (group: ToolGroup<ToolRef>) =>
  group.tools.every(tool => isSelected(tool.eqp_id))

// "Everything selected" is stored as an empty list, so a tool added to the fleet
// later shows up instead of being excluded by a selection saved before it
// existed. See resolveSelection in utils/tttmFleetSubset.
const isCustomised = computed(() => props.selected.length !== props.tools.length)

// Every change funnels through here: fleet order first, then the all-selected
// collapse, so no caller has to remember either rule.
//
// A one-tool comparison is not a comparison, so the last removal is refused the
// way utils/fab.ts refuses to drop the last fab. Refusing rather than clamping
// keeps the chips honest — the click simply does nothing.
const apply = (wanted: Set<string>) => {
  const next = orderSelection(fleetIds.value, wanted)
  if (next.length < 2) return
  emit('update:selected', next.length === props.tools.length ? [] : next)
}

const toggle = (eqp: string) => {
  const wanted = new Set(props.selected)
  if (!wanted.delete(eqp)) wanted.add(eqp)
  apply(wanted)
}

// A fully-selected series deselects; anything else selects the whole series.
// The asymmetry is deliberate — "add the rest of the CG6300s" is the common
// intent, and a half-selected group toggling to empty would throw away picks
// the user just made.
const toggleGroup = (group: ToolGroup<ToolRef>) => {
  const wanted = new Set(props.selected)
  const drop = isWholeGroupSelected(group)
  for (const tool of group.tools) {
    if (drop) wanted.delete(tool.eqp_id)
    else wanted.add(tool.eqp_id)
  }
  apply(wanted)
}

// Empty IS everything — the same collapse `apply` performs, said directly
// because there is no set to order first.
const selectAll = () => emit('update:selected', [])

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
