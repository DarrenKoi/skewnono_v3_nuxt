<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <!-- 비교 대상 — 무엇을 비교할지: 장비와 recipe. 두 실험실 페이지가 같은 저장
         설정을 쓰므로 한쪽에서 바꾸면 다른 쪽도 같이 바뀝니다. 이 둘이 정해져야
         측정 데이터가 오고, parameter 는 그 데이터에서 고르므로 아래 분석 조건 바에
         있습니다. -->
    <div class="min-w-0">
      <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p class="sk-panel-title">
          비교 대상
        </p>
        <p class="sk-hint">
          {{ hint }}
        </p>
      </div>

      <!-- Tools get the wider column: a fab runs up to ~7 model-group
             dropdowns of 148px, while the recipe is one cell whose popper
             widens on its own. -->
      <div class="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div class="min-w-0">
          <p class="mb-1.5 sk-label">
            장비 · 모델 그룹
          </p>
          <!-- One dropdown per model code, not a chip per tool. A fab carries
                 up to ~18 CD-SEMs; laid out as chips they filled the width of the
                 page. The trigger always says "몇 대 중 몇 대" so the collapsed
                 state never hides how much is selected. -->
          <div class="flex flex-wrap gap-1.5">
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

              <!-- The tool's standing against the WHOLE fleet's consensus, so
                     the choice is informed before it is made. Deliberately the
                     payload's own number rather than the re-based one the charts
                     below show: re-basing is defined against a selection, and
                     this row is where the selection gets decided. -->
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

          <!-- An empty roster is two different facts, and the loading one must
                 not read as "this fab has no tools": the skew payload carries the
                 roster, so there is nothing to group until it lands. -->
          <p
            v-if="!groups.length"
            class="sk-field-label"
          >
            {{ pending ? '장비 목록을 불러오는 중입니다.' : '이 FAB 의 장비 목록이 비어 있습니다.' }}
          </p>
          <div
            v-else
            class="mt-2 flex items-center gap-2"
          >
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
            v-if="groups.length && selected.length < 2"
            class="mt-1 text-xs text-(--sk-bad)"
          >
            비교하려면 2대 이상이어야 합니다.
          </p>
        </div>

        <!-- The recipe picker arrives as a SLOT rather than through relayed
               props. That relay existed once and cost a release: two newly
               added props were not declared on the wrapper, so Vue turned them
               into fallthrough attributes on its root div and the picker
               silently used its own defaults — working on the page that
               mounts ScopeRecipe directly and doing nothing on the page that
               went through the wrapper. Slotted, there is no relay to forget. -->
        <div class="min-w-0">
          <slot name="recipe" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatSignedNm } from '~/utils/tttmLimits'
import { groupToolsByModel, orderSelection, type ToolGroup } from '~/utils/tttmToolGroups'
import type { ToolRef } from '~/composables/useTttmApi'

/**
 * 비교 대상 — the one control surface both lab pages scope themselves with.
 *
 * Full-width and above the results rather than a side rail: the results are
 * GATED on this bar (nothing renders until a recipe is picked), so it is the
 * first thing read and the first thing acted on, and a page-wide bar is what
 * puts it in reading order. See DESIGN.md §Layout — the scope-bar rule.
 *
 * The tool half lives here; the recipe half arrives as a slot. The parameter
 * and the page-specific control (tolerance knob, 튜닝할 장비) are NOT here —
 * they act on the measurement data this bar's choice selects, so they sit in
 * the 분석 조건 bar below (`EbeamAnalysisBar`), which stays inert until a
 * recipe is picked.
 */

// NuxtUI pins a menu to its trigger (`w-(--reka-select-trigger-width)` in
// .nuxt/ui/select-menu.ts), and these triggers are 148px — narrower than the
// old rail, because a row of them has to fit across the bar. An eqp_id plus its
// consensus residual does not fit in 148px, so the MENU widens instead of the
// trigger, bounded by the viewport.
const MENU_CONTENT = 'w-auto min-w-full max-w-[min(24rem,calc(100vw-2rem))]'

const props = withDefaults(defineProps<{
  tools: ToolRef[]
  /** Resolved ids actually in play — an empty stored selection already expanded. */
  selected: string[]
  /** Fleet-wide consensus deviation per tool, for the dropdown rows. */
  deviations: Record<string, number>
  /** The payload carrying the roster is still in flight — empty is not yet empty. */
  pending?: boolean
  hint?: string
}>(), {
  pending: false,
  hint: '고른 장비와 recipe 로 다시 계산합니다. 이 설정은 이 브라우저에 저장되고, TTTM · PM 튜닝 두 페이지가 함께 씁니다.'
})

const emit = defineEmits<{
  (e: 'update:selected', value: string[]): void
  (e: 'update:recipeId', value: string | null): void
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
// recipe-local, so a stored one outliving its recipe names nothing. The
// parameter is not this bar's to emit; the store's setRecipe nulls it, which
// is the one rule both pages already rely on.
const reset = () => {
  emit('update:selected', [])
  emit('update:recipeId', null)
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
