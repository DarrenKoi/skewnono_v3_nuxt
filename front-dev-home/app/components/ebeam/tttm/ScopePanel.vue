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
        :items="idsIn(group)"
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
          >{{ formatSignedNm(deviations[item]!) }}</span>
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
              @click="applyGroup(group, idsIn(group))"
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

    <!-- The recipe/parameter pair arrives as a SLOT, for the same reason the
         tolerance knob below does: this panel owns no part of that control. It
         relayed eight props and two emits through to ScopeRecipe, and the cost
         of that was paid on 2026-08-18 — two newly added props were not
         declared here, so Vue turned them into fallthrough attributes on the
         root div and the picker silently used its own defaults. The features
         worked on pm-tune, which mounts ScopeRecipe directly, and did nothing
         on this page. Slotted, there is no relay to forget to update. -->
    <div class="mt-4">
      <slot name="recipe" />
    </div>

    <!-- The knob arrives as a slot rather than through three props and an emit.
         Relaying it cost nothing to write and everything to drag: a prop that
         changes on every `input` event re-renders THIS component, and with it
         every model-group `USelectMenu` below — at ~60 fps, for a control that
         needs no state from here at all. Slotted, the panel simply hosts it. -->
    <div class="mt-4 border-t border-(--sk-border-soft) pt-3.5">
      <slot name="tolerance" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatSignedNm } from '~/utils/tttmLimits'
import { groupToolsByModel, orderSelection, type ToolGroup } from '~/utils/tttmToolGroups'
import type { ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  tools: ToolRef[]
  /** Resolved ids actually in play — empty stored selection already expanded. */
  selected: string[]
  /** Fleet-wide consensus deviation per tool, for the dropdown rows. */
  deviations: Record<string, number>
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: string[]): void
  (e: 'update:recipeId' | 'update:parameter', value: string | null): void
}>()

const fleetIds = computed(() => props.tools.map(t => t.eqp_id))
const groups = computed(() => groupToolsByModel(props.tools))

// Set-backed, and the per-group id lists and picks are computed once per
// selection change rather than per render: `pickedIn` feeds both a
// `:model-value` and a label, so an array rebuilt in the template handed every
// USelectMenu a new identity on each pass and re-rendered the whole menu
// subtree. A fab runs up to 18 tools across ~7 model groups.
const selectedSet = computed(() => new Set(props.selected))
const isSelected = (eqp: string) => selectedSet.value.has(eqp)

const groupIds = computed(() =>
  new Map(groups.value.map(g => [g.model, g.tools.map(t => t.eqp_id)]))
)
const groupPicks = computed(() =>
  new Map(
    groups.value.map(g => [g.model, (groupIds.value.get(g.model) ?? []).filter(isSelected)])
  )
)
const idsIn = (group: ToolGroup<ToolRef>) => groupIds.value.get(group.model) ?? []
const pickedIn = (group: ToolGroup<ToolRef>) => groupPicks.value.get(group.model) ?? []

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

// Clearing the recipe clears the parameter with it — a parameter name is
// recipe-local, so a stored one outliving its recipe names nothing. The store
// enforces this too (setRecipe nulls it); emitting both keeps 기본값으로 honest
// on its own terms rather than relying on the writer downstream.
const reset = () => {
  emit('update:selected', [])
  emit('update:recipeId', null)
  emit('update:parameter', null)
}

// A group with nothing picked stays outlined; any pick fills it with the brand,
// which is DESIGN.md's FILTER role (`sk-chip`) — these narrow the data on this
// page rather than navigating anywhere.
//
// The `[&_svg]` reach is for the chevron: NuxtUI gives the trailing icon its own
// dimmed colour rather than letting it inherit, so on the terracotta fill it
// renders near-black — legible enough in light mode to miss, and clearly wrong
// in dark. `--sk-brand-fg` does not invert (brand is dark in both themes), so
// one value is right for both.
const triggerClass = (group: ToolGroup<ToolRef>) =>
  pickedIn(group).length
    ? 'bg-(--sk-brand) text-(--sk-brand-fg) ring-(--sk-brand) hover:bg-(--sk-brand)'
    + ' [&_svg]:text-(--sk-brand-fg)'
    : ''
</script>
