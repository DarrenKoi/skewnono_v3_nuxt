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
  <div class="flex items-start gap-2">
    <span class="mt-1.5 shrink-0 sk-meta">파라미터</span>
    <div
      role="group"
      aria-label="분석 파라미터"
      class="flex flex-wrap items-center gap-1"
    >
      <button
        v-for="o in options"
        :key="o.parameter"
        type="button"
        :aria-pressed="o.parameter === modelValue"
        :title="o.covered === o.loaded
          ? `${paramLabel(o.parameter)} · 측정 ${o.loaded}개 모두 보유`
          : `${paramLabel(o.parameter)} · 측정 ${o.loaded}개 중 ${o.covered}개만 보유`"
        class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) px-2.5 font-mono text-[11px] leading-none transition-colors"
        :class="o.parameter === modelValue
          ? 'bg-(--sk-ink) font-semibold text-(--sk-ink-fg)'
          : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="emit('update:modelValue', o.parameter)"
      >
        {{ paramLabel(o.parameter) }}
        <!-- Partial coverage only. Kept INSIDE the button rather than beside it
             so the chip stays one hit target. On the selected chip it rides the
             ink fill at reduced opacity; elsewhere it is a muted count. -->
        <span
          v-if="o.covered < o.loaded"
          class="text-[10px] tabular-nums opacity-60"
        >{{ o.covered }}/{{ o.loaded }}</span>
      </button>
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
