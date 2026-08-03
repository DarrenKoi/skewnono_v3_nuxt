<template>
  <!-- Every parameter the set carries, laid out in the open like the 측정 개요
       파라미터 요약 — a dropdown hid the list behind a click, and the list IS
       the overview of what this set can be compared on.

       Coverage is shown on every chip so a silent drop becomes a visible one:
       picking a parameter 22 of 30 measurements carry should look different
       from picking one they all share. -->
  <div
    role="group"
    aria-label="분석 파라미터"
    class="flex flex-wrap items-center gap-1.5"
  >
    <button
      v-for="o in options"
      :key="o.parameter"
      type="button"
      :aria-pressed="o.parameter === modelValue"
      class="rounded-(--sk-r-chip) px-2 py-1 font-mono text-[11px] transition-colors"
      :class="o.parameter === modelValue
        ? 'bg-(--sk-accent-soft) font-semibold text-(--sk-accent)'
        : 'bg-(--sk-chip-bg) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="emit('update:modelValue', o.parameter)"
    >
      {{ paramLabel(o.parameter) }}
      <span class="ml-1 tabular-nums opacity-70">{{ o.covered }}/{{ o.loaded }}</span>
    </button>
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
