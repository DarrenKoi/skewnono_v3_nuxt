<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <!-- 비교 대상 — 어떤 측정 데이터를 볼지: recipe 와 얼마나 모을지(수집 기간).
         두 실험실 페이지가 같은 저장 설정을 쓰므로 한쪽에서 바꾸면 다른 쪽도 같이
         바뀝니다. 이 둘이 정해져야 측정 데이터가 오고, 장비(아래 장비 모델 그룹)와
         parameter(분석 조건)는 그 데이터에서 고릅니다. -->
    <div class="min-w-0">
      <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p class="sk-panel-title">
          비교 대상
        </p>
        <p class="sk-hint">
          {{ hint }}
        </p>
      </div>

      <!-- The recipe is one cell whose popper widens on its own; the window is
           four chips and takes only the width it needs. -->
      <div class="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
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

        <!-- Same slot rule as the recipe, same reason. -->
        <div class="min-w-0">
          <slot name="window" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 비교 대상 — the first of the three bars both lab pages scope themselves with.
 *
 * Full-width and above the results rather than a side rail: the results are
 * GATED on this bar (nothing renders until a recipe is picked), so it is the
 * first thing read and the first thing acted on, and a page-wide bar is what
 * puts it in reading order. See DESIGN.md §Layout — the scope-bar rule.
 *
 * Recipe and 수집 기간 only, since 2026-08-27. The tool cell moved out to its
 * own bar (`EbeamToolGroupBar`): which tools to compare is decided AMONG the
 * roster the recipe's payload returns, so it is the second step, not a third
 * cell of the first. The parameter and the page-specific control (tolerance
 * knob, 튜닝할 장비) sit in the 분석 조건 bar (`EbeamAnalysisBar`) below.
 */
withDefaults(defineProps<{
  hint?: string
}>(), {
  hint: '고른 recipe · 수집 기간의 측정 데이터로 계산합니다. 이 설정은 이 브라우저에 저장되고, TTTM · PM 플래닝 두 페이지가 함께 씁니다.'
})
</script>
