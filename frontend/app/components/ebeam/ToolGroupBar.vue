<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <!-- 장비 모델 그룹 — 누구를 비교할지. 비교 대상(recipe · 수집 기간)이 측정
         데이터를 정하고, 이 바는 그 데이터 안에서 비교에 넣을 장비를 고릅니다.
         두 실험실 페이지가 같은 저장 설정을 쓰므로 한쪽에서 바꾸면 다른 쪽도
         같이 바뀝니다. -->
    <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <p class="sk-panel-title flex items-center gap-1.5">
        장비 모델 그룹
        <!-- The skew payload behind these dropdowns is slow at the office
             (hundreds of MinIO GETs), and a refetch keeps the previous roster
             on screen — so the spinner, not the roster, is what says "still
             computing". -->
        <UIcon
          v-if="pending"
          name="i-lucide-loader-circle"
          class="h-3.5 w-3.5 animate-spin text-(--sk-ink-muted)"
          aria-label="불러오는 중"
        />
      </p>
      <p class="sk-hint">
        {{ hint }}
      </p>
    </div>

    <!-- One dropdown per model code, not a chip per tool. A fab carries up to
         ~18 CD-SEMs; laid out as chips they filled the width of the page. The
         trigger always says "몇 대 중 몇 대" so the collapsed state never hides
         how much is selected. -->
    <div class="mt-3 flex flex-wrap gap-1.5">
      <USelectMenu
        v-for="group in groups"
        :key="group.model"
        :model-value="pickedIn(group)"
        multiple
        ignore-filter
        :reset-search-term-on-select="false"
        :items="idsIn(group)"
        :search-input="group.tools.length > 6 ? { placeholder: 'eqp_id 검색…' } : false"
        :ui="{ content: MENU_CONTENT, itemTrailingIcon: 'hidden' }"
        color="neutral"
        variant="outline"
        trailing-icon="i-lucide-chevron-down"
        class="w-[148px]"
        :class="triggerClass(group)"
        @update:model-value="applyGroup(group, $event)"
      >
        <template #default>
          <span class="truncate font-semibold">{{ group.model }}</span>
          <span
            class="ml-auto pl-1 font-mono text-[13px] tabular-nums"
            :class="pickedIn(group).length ? 'opacity-80' : 'text-(--sk-ink-subtle)'"
          >{{ pickedIn(group).length }}/{{ group.tools.length }}</span>
        </template>

        <template #item-leading="{ item }">
          <AppSelectCheck :checked="isSelected(item)" />
        </template>

        <!-- The tool's standing against the WHOLE fleet's consensus, so the
             choice is informed before it is made. Deliberately the payload's
             own number rather than the re-based one the charts below show:
             re-basing is defined against a selection, and this row is where
             the selection gets decided. -->
        <template #item-trailing="{ item }">
          <span
            v-if="deviations[item] !== undefined"
            class="ml-auto font-mono text-xs tabular-nums text-(--sk-ink-muted)"
            title="장비 그룹 전체 기준 consensus 잔차"
          >{{ formatSignedNm(deviations[item]!) }}</span>
          <span
            v-else-if="isAnswered(item)"
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

    <!-- An empty roster is two different facts, and the loading one must not
         read as "this fab has no tools": the skew payload carries the roster,
         so there is nothing to group until it lands. -->
    <p
      v-if="!groups.length"
      class="mt-2 sk-field-label"
    >
      {{ pending ? '장비 목록을 불러오는 중입니다.' : '이 FAB 의 장비 목록이 비어 있습니다.' }}
    </p>
    <div
      v-else
      class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1"
    >
      <span class="sk-field-label">
        {{ tools.length }}대 중 <strong class="font-mono tabular-nums text-(--sk-ink)">{{ selected.length }}대</strong> 선택
      </span>
      <span
        v-if="selected.length < 2"
        class="text-xs text-(--sk-bad)"
      >
        비교하려면 2대 이상이어야 합니다.
      </span>
      <span class="ml-auto flex items-center gap-1">
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-list-checks"
          :disabled="!isCustomised"
          @click="emit('update:selected', null)"
        >
          전체 선택
        </UButton>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-eraser"
          :disabled="selected.length === 0"
          @click="emit('update:selected', [])"
        >
          전체 해제
        </UButton>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatSignedNm } from '~/utils/tttmLimits'
import { groupToolsByModel, orderSelection, type ToolGroup } from '~/utils/tttmToolGroups'
import type { ToolRef } from '~/composables/useTttmApi'

/**
 * 장비 모델 그룹 — which tools are in the comparison.
 *
 * Its own bar since 2026-08-27, between 비교 대상 (recipe · 수집 기간) and
 * 분석 조건: the three are three steps — what data, whose tools, how to judge —
 * and the tool cell had shared a row with the recipe, where it read as one
 * choice among three and its 해제 was quietly refused (see `apply`). See
 * DESIGN.md §Layout — the scope-bar rule.
 *
 * Selection is `string[] | null`: null is the whole fleet (a fresh user, and
 * what "전체 선택" writes), an array is exactly those tools — including none.
 */

// NuxtUI pins a menu to its trigger (`w-(--reka-select-trigger-width)` in
// .nuxt/ui/select-menu.ts), and these triggers are 148px — narrower than the
// old rail, because a row of them has to fit across the bar. An eqp_id plus its
// consensus residual does not fit in 148px, so the MENU widens instead of the
// trigger, bounded by the viewport.
const MENU_CONTENT = 'w-auto min-w-full max-w-[min(24rem,calc(100vw-2rem))]'

const props = withDefaults(defineProps<{
  tools: ToolRef[]
  /** Resolved ids actually in play — a null stored selection already expanded. */
  selected: string[]
  /** Fleet-wide consensus deviation per tool, for the dropdown rows. */
  deviations: Record<string, number>
  /** The payload carrying the roster is still in flight — empty is not yet empty. */
  pending?: boolean
  /**
   * The tools the payload actually answered for. A tool outside it has no
   * deviation because it was never REQUESTED (TTTM narrows the request to
   * the picked tools since 2026-08-28), which is not "측정 없음" — so the badge
   * is only drawn inside this set. Omitted = every tool was asked for.
   */
  answered?: string[]
  hint?: string
}>(), {
  pending: false,
  answered: undefined,
  hint: '비교에 넣을 장비를 모델 그룹별로 고릅니다 — 그룹 전체를 켜고 끄거나, 펼쳐서 한 대씩 고릅니다. 이 설정은 이 브라우저에 저장됩니다.'
})

const emit = defineEmits<{
  (e: 'update:selected', value: string[] | null): void
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

const answeredSet = computed(() => props.answered ? new Set(props.answered) : null)
const isAnswered = (eqp: string) => answeredSet.value?.has(eqp) ?? true

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

const isCustomised = computed(() => props.selected.length !== props.tools.length)

// Every change funnels through here: fleet order first, then the all-selected
// collapse to null, so no caller has to remember either rule.
//
// No lower bound. This used to refuse any change that left fewer than two
// tools, which is why 해제 "did not work": on a fab whose tools are one model
// group, or when the other groups held one tool, the click was silently
// dropped — and clearing the last group produced `[]`, which the store then
// read as "all". The comparison needs two tools, and the views say so
// ("2대 이상이어야 합니다") in place of results; the control itself stays
// honest and does what was clicked.
const apply = (wanted: Set<string>) => {
  const next = orderSelection(fleetIds.value, wanted)
  emit('update:selected', next.length === props.tools.length ? null : next)
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

// A group with nothing picked stays outlined; any pick fills it with the brand,
// which is DESIGN.md's FILTER role — these narrow the data on this page rather
// than navigating anywhere.
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
