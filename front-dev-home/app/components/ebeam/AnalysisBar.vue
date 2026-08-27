<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:gap-5">
      <!-- 분석 조건 — 비교 대상이 정해져 측정 데이터가 온 뒤에야 뜻이 생기는 선택.
           parameter 는 그 데이터에서 읽은 목록이고, 오른쪽 칸은 페이지마다 다른
           조건(판정 임계값 · 튜닝할 장비)입니다. -->
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p class="sk-panel-title">
            분석 조건
          </p>
          <p class="sk-hint">
            {{ hint }}<template v-if="note">
              {{ note }}
            </template>
          </p>
        </div>

        <!-- Capped rather than stretched: one dropdown across the full bar
             width reads as a text field, and a parameter name is short. -->
        <div class="mt-3 max-w-md">
          <slot name="parameter" />
        </div>
      </div>

      <!-- 판정 임계값(TTTM) 또는 튜닝 장비(pm-planning) — parameter 와 같은 단계의
           선택이지만 서로 다른 물음이라, 같은 바 안에서 선으로 갈라 둡니다.
           The slot hands the control its `disabled`, so the collapse of the
           lock into a boolean is written once, here. -->
      <div class="shrink-0 border-t border-(--sk-border-soft) pt-4 xl:w-[264px] xl:border-t-0 xl:border-l xl:pt-0 xl:pl-5">
        <slot
          name="trailing"
          :disabled="disabled"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AnalysisLock } from '~/utils/tttmRecipeScope'

/**
 * The second bar of the two lab pages, under 비교 대상 (`EbeamScopeBar`).
 *
 * The split follows the procedure: pick the tools and the recipe, THEN the
 * measurement rows arrive, and only then is there a parameter list to pick
 * from — so the parameter cannot honestly sit beside the recipe as one choice
 * in two steps. The bar is always mounted and its controls are DISABLED until
 * a recipe is picked: hidden, the second step did not exist until the first
 * was taken, and the page's layout jumped when it appeared; disabled, the
 * procedure reads as two steps from the start and the parameter's caption
 * says which step is missing. See DESIGN.md §Layout — the scope-bar rule.
 *
 * `lock` is the one input; it comes from useTttmScope, so both pages share
 * the rule. The parameter cell reads the full reason (it captions it); the
 * trailing control gets the boolean collapse through its slot.
 *
 * Both cells arrive as slots for the reason ScopeBar's recipe cell does: a
 * prop relay through a wrapper is a place to forget a prop, and the knob in
 * the trailing cell fires on every drag frame.
 */
const props = withDefaults(defineProps<{
  lock: AnalysisLock
  hint?: string
  /** A page-specific sentence appended to the hint. */
  note?: string
}>(), {
  hint: '비교 대상의 측정 데이터에서 읽은 parameter 로 판정 조건을 정합니다.',
  note: undefined
})

// Inert for a REASON, not for a moment: while the list is merely loading the
// trailing control still acts on a stale-but-available payload, and a slider
// that greys out on every refetch reads as broken.
const disabled = computed(() => props.lock === 'no-recipe' || props.lock === 'no-data')
</script>
