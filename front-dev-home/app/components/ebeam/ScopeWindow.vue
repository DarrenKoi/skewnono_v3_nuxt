<template>
  <div class="min-w-0">
    <p class="mb-1.5 sk-label">
      수집 기간
    </p>
    <!-- Chips, not a dropdown: three fixed choices the reader should see all
         of at once, and picking one narrows the data on this page — the
         FILTER role, so the active chip takes the brand fill like the model
         dropdowns beside it (DESIGN.md §Selection Primitives). -->
    <div
      role="group"
      aria-label="수집 기간"
      class="flex flex-wrap gap-1.5"
    >
      <SkChip
        v-for="weeks in WINDOW_WEEKS"
        :key="weeks"
        :label="`${weeks}주`"
        :active="windowWeeks === weeks"
        @click="emit('update:windowWeeks', weeks)"
      />
    </div>
    <!-- What the choice costs, in the reader's terms. The server gathers more
         RUNS per tool as the window widens (not merely an older cut-off), so
         a wider window is more evidence — at the price of mixing in a state
         the tool may since have left. -->
    <p class="mt-2 sk-field-label leading-relaxed">
      최근 <strong class="font-mono tabular-nums text-(--sk-ink)">{{ windowDays(windowWeeks) }}일</strong>의 run 을 모읍니다 · 길수록 근거가 늘지만 지난 상태가 섞입니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { WINDOW_WEEKS, windowDays, type WindowWeeks } from '~/utils/analysisWindow'

/**
 * 수집 기간 — how many weeks of runs the server gathers for the whole scope.
 *
 * Third cell of 비교 대상 rather than a 분석 조건 control: it decides WHICH
 * measurement rows exist to analyse (it re-fetches the recipe picker and the
 * check alike), so it is part of stating what to compare, not of acting on
 * the answer. Slotted into the bar the way the recipe picker is — see the
 * relay note on ScopeBar's recipe slot.
 */
defineProps<{
  /** The shared scope's window — one of WINDOW_WEEKS, already normalised. */
  windowWeeks: WindowWeeks
}>()

const emit = defineEmits<{
  (e: 'update:windowWeeks', value: WindowWeeks): void
}>()
</script>
