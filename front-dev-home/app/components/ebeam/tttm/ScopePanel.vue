<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <p class="sk-panel-title">
      비교 범위
    </p>
    <p class="mt-1 sk-hint">
      고른 장비와 recipe 로 다시 계산합니다. 이 설정은 이 브라우저에 저장됩니다.
    </p>

    <p class="mt-4 mb-1.5 sk-label">
      장비 · 모델 그룹
    </p>
    <!-- One dropdown per model code, not a chip per tool. A fab carries up to
         ~18 CD-SEMs; laid out as chips they filled the width of the page, which
         is what the 392px rail cannot afford. The trigger always says "몇 대 중
         몇 대" so the collapsed state never hides how much is selected. -->
    <div class="flex flex-col gap-1.5">
      <USelectMenu
        v-for="group in groups"
        :key="group.model"
        :model-value="pickedIn(group)"
        multiple
        ignore-filter
        :reset-search-term-on-select="false"
        :items="group.tools.map(t => t.eqp_id)"
        :search-input="group.tools.length > 6 ? { placeholder: 'eqp_id 검색…' } : false"
        :ui="{ itemTrailingIcon: 'hidden' }"
        color="neutral"
        variant="outline"
        trailing-icon="i-lucide-chevron-down"
        class="w-full"
        :class="triggerClass(group)"
        @update:model-value="applyGroup(group, $event)"
      >
        <template #default>
          <span class="font-semibold">{{ group.model }}</span>
          <span
            class="ml-auto pr-1 font-mono text-[13px] tabular-nums"
            :class="pickedIn(group).length ? 'opacity-80' : 'text-(--sk-ink-subtle)'"
          >{{ pickedIn(group).length }}/{{ group.tools.length }}</span>
        </template>

        <template #item-leading="{ item }">
          <AppSelectCheck :checked="isSelected(item)" />
        </template>

        <!-- The tool's standing against the WHOLE fleet's consensus, so the
             choice is informed before it is made. Deliberately the payload's
             own number rather than the re-based one the charts below show:
             re-basing is defined against a selection, and this row is how the
             selection gets decided. -->
        <template #item-trailing="{ item }">
          <span
            v-if="deviations[item] !== undefined"
            class="ml-auto font-mono text-xs tabular-nums text-(--sk-ink-muted)"
            title="장비 그룹 전체 기준 consensus 잔차"
          >{{ signed(deviations[item]!) }}</span>
          <span
            v-else
            class="ml-auto sk-signal-badge bg-(--sk-bad-soft) text-(--sk-bad)"
          >측정 없음</span>
        </template>

        <template #content-bottom>
          <div
            class="flex items-center gap-1 border-t border-(--sk-border-soft) p-1"
            @keydown.enter.stop
            @keydown.space.stop
          >
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-list-checks"
              :disabled="pickedIn(group).length === group.tools.length"
              @click="applyGroup(group, group.tools.map(t => t.eqp_id))"
            >
              {{ group.model }} 전체
            </UButton>
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-eraser"
              :disabled="pickedIn(group).length === 0"
              @click="applyGroup(group, [])"
            >
              해제
            </UButton>
          </div>
        </template>
      </USelectMenu>
    </div>

    <div class="mt-2 flex items-center gap-2">
      <span class="sk-field-label">
        {{ tools.length }}대 중 <strong class="font-mono tabular-nums text-(--sk-ink)">{{ selected.length }}대</strong> 선택
      </span>
      <button
        v-if="isCustomised"
        type="button"
        class="ml-auto sk-field-label underline underline-offset-2 hover:text-(--sk-ink)"
        @click="reset"
      >
        기본값으로
      </button>
    </div>
    <p
      v-if="selected.length < 2"
      class="mt-1 text-xs text-(--sk-bad)"
    >
      비교하려면 2대 이상이어야 합니다.
    </p>

    <p class="mt-4 mb-1.5 sk-label">
      RECIPE
    </p>
    <!-- Searchable, not a plain <select>: R3 alone answers with 50,000 recipe
         names, and rendering that many <option> nodes locks the page. Search is
         the only way to reach one, so the list is filtered and capped. -->
    <USelectMenu
      v-model:search-term="searchTerm"
      :model-value="recipeId ?? ALL_RECIPES"
      ignore-filter
      :items="recipeItems"
      :search-input="{ placeholder: 'recipe 이름 검색 — 비우면 전체' }"
      :loading="recipesPending"
      icon="i-lucide-search"
      color="neutral"
      variant="outline"
      class="w-full"
      @update:model-value="onRecipe($event === ALL_RECIPES ? '' : String($event))"
    />
    <p class="mt-1.5 sk-field-label">
      <template v-if="overflowed">
        {{ matchCount.toLocaleString() }}건 중 {{ RECIPE_LIMIT }}건만 표시합니다 — 더 좁혀서 검색하십시오.
      </template>
      <template v-else>
        {{ recipeNames.length.toLocaleString() }}건 · recipe 를 고르면 그 recipe 만으로 다시 계산합니다.
      </template>
    </p>

    <div class="mt-4 border-t border-(--sk-border-soft) pt-3.5">
      <EbeamTttmToleranceKnob
        :model-value="tolerance"
        :range="range"
        :tolerance-index="toleranceIndex"
        @update:model-value="emit('update:tolerance', $event)"
      />
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
  /** Fleet-wide consensus deviation per tool, for the dropdown rows. */
  deviations: Record<string, number>
  recipeId: string | null
  recipeNames: string[]
  recipesPending: boolean
  tolerance: number
  range: { min: number, max: number, step: number }
  toleranceIndex: number
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: string[]): void
  (e: 'update:recipeId', value: string | null): void
  (e: 'update:tolerance', value: number): void
}>()

const fleetIds = computed(() => props.tools.map(t => t.eqp_id))
const groups = computed(() => groupToolsByModel(props.tools))

const isSelected = (eqp: string) => props.selected.includes(eqp)
const pickedIn = (group: ToolGroup<ToolRef>) =>
  group.tools.map(t => t.eqp_id).filter(isSelected)

// "Everything selected" is stored as an empty list, so a tool added to the fleet
// later shows up instead of being excluded by a selection saved before it
// existed. See resolveSelection in utils/tttmFleetSubset.
const isCustomised = computed(() => props.selected.length !== props.tools.length)

// Every change funnels through here: fleet order first, then the all-selected
// collapse, so no caller has to remember either rule.
//
// A one-tool comparison is not a comparison, so the last removal is refused the
// way utils/fab.ts refuses to drop the last fab. Refusing rather than clamping
// keeps the control honest — the click simply does nothing.
const apply = (wanted: Set<string>) => {
  const next = orderSelection(fleetIds.value, wanted)
  if (next.length < 2) return
  emit('update:selected', next.length === props.tools.length ? [] : next)
}

// A group's menu speaks only for its own tools, so the other groups' picks are
// carried across unchanged. Without this the second dropdown would silently
// clear the first one.
const applyGroup = (group: ToolGroup<ToolRef>, picked: unknown) => {
  const kept = new Set(props.selected)
  for (const tool of group.tools) kept.delete(tool.eqp_id)
  for (const eqp of picked as string[]) kept.add(eqp)
  apply(kept)
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

const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`

// A group with nothing picked stays outlined; any pick fills it with the brand,
// which is DESIGN.md's FILTER role (`sk-chip`) — these narrow the data on this
// page rather than navigating anywhere.
const triggerClass = (group: ToolGroup<ToolRef>) =>
  pickedIn(group).length
    ? 'bg-(--sk-brand) text-(--sk-brand-fg) ring-(--sk-brand) hover:bg-(--sk-brand)'
    : ''
</script>
