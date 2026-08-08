<template>
  <!-- Every parameter the set carries, laid out in the open like the 측정 개요
       파라미터 요약 — a dropdown hid the list behind a click, and the list IS
       the overview of what this set can be compared on.

       Coverage is shown only where it is NOT complete. That serves the rule the
       first version was reaching for — "picking a parameter 22 of 30
       measurements carry should look different from picking one they all share"
       — better, not worse: when every chip wore an `n/n` badge, the partial ones
       had to be found by reading, and a row of identical `30/30`s was pure
       noise. Now a coverage number appearing AT ALL is the signal.

       The badge stays MUTED rather than warning-toned. A cross-recipe set is
       partial on nearly every parameter, so a semantic tone fires on all of
       them at once and stops distinguishing anything — an amber wall is the
       same non-signal the `30/30` wall was. The set-level warning about mixed
       recipes is what says "this set is a weak basis"; a per-chip tone would
       only repeat it sixteen times.

       The 파라미터 label is not decoration: without it a bare wrap of mono chips
       under the integrity alerts reads as output, not as the control that
       drives every chart on the page. -->
  <div class="dashboard-surface flex flex-col gap-2 rounded-(--sk-r-card) px-3 py-2.5">
    <!-- On its own surface, under a full panel title. A bare label plus a chip
         row sat at the same visual weight as the integrity alerts stacked above
         it, so the one control every chart on this page obeys read as another
         notice to skim past. The panel is the distinction; the title states the
         job the label was already trying to do. -->
    <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <h3 class="sk-panel-title">
        파라미터
      </h3>
      <p class="sk-hint">
        아래 모든 차트가 선택한 파라미터를 따릅니다.
      </p>
    </div>
    <div
      role="group"
      aria-label="분석 파라미터"
      class="flex flex-wrap items-center gap-1.5"
    >
      <!-- SkChip rather than a hand-rolled button: DESIGN.md's selection
           primitives route "narrows data on the same page" to sk-chip, and this
           narrows every chart below to one parameter. `tone="ink"` keeps the ink
           fill the hand-rolled version had, so only the size changes. The label
           stays mono because a parameter is a raw backend field name, not a word.

           Coverage rides the chip's own `count` slot — still partial-only, still
           muted, both for the reasons in the header comment. -->
      <SkChip
        v-for="o in options"
        :key="o.parameter"
        tone="ink"
        :active="o.parameter === modelValue"
        :count="o.covered < o.loaded ? `${o.covered}/${o.loaded}` : null"
        :title="o.covered === o.loaded
          ? `${paramLabel(o.parameter)} · 측정 ${o.loaded}개 모두 보유`
          : `${paramLabel(o.parameter)} · 측정 ${o.loaded}개 중 ${o.covered}개만 보유`"
        @click="emit('update:modelValue', o.parameter)"
      >
        <span class="font-mono">{{ paramLabel(o.parameter) }}</span>
      </SkChip>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SetParamOption } from '~/utils/skewvoirAnalysis/timeSeries'
import { paramLabel } from '~/utils/skewvoirAnalysis/paramOrder'

defineProps<{
  options: SetParamOption[]
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [parameter: string] }>()
</script>
