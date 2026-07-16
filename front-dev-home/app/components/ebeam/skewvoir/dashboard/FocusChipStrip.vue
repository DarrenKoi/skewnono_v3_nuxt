<template>
  <div
    v-if="analysis.msrList.value.length >= 2"
    class="flex flex-wrap items-center gap-2 rounded-(--sk-r-card) border border-(--sk-border) bg-(--sk-muted-surface) px-3 py-2"
  >
    <span class="sk-eyebrow">
      비교 세트
    </span>
    <button
      v-for="chip in chips"
      :key="chip.msr"
      type="button"
      class="inline-flex max-w-56 items-center gap-1.5 rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-xs transition-colors duration-200"
      :class="chip.active
        ? 'bg-(--sk-brand) font-semibold text-(--sk-brand-fg)'
        : 'border border-(--sk-border) bg-(--sk-surface) text-(--sk-ink-muted) hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)'"
      :aria-pressed="chip.active"
      :title="chip.label"
      @click="analysis.setFocusedMsr(chip.msr)"
    >
      <span class="truncate">{{ chip.label }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// Chip order follows the URL `msrs` list verbatim (authored order). Labels
// come from meas_hist (rowByMsr/msrLabel) only — never require an msr_file
// fetch, so rendering the strip is free even before any focus file loads.
const chips = computed(() => {
  const focusMsr = props.analysis.focusMsr.value
  return props.analysis.msrList.value.map(msr => ({
    msr,
    label: props.analysis.msrLabel(msr),
    active: msr === focusMsr
  }))
})
</script>
