<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <span class="font-mono text-[9.5px] uppercase tracking-wide text-(--sk-ink-subtle)">파라미터</span>
    <button
      v-for="c in chips"
      :key="c.parameter"
      type="button"
      class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) border px-2 py-1 font-mono text-[11px] transition-colors"
      :class="c.parameter === activeParam
        ? 'border-(--sk-brand) bg-(--sk-brand)/12 font-semibold text-zinc-900 dark:text-zinc-100'
        : 'border-(--sk-border-soft) text-(--sk-ink-muted) hover:bg-(--sk-chip-bg)'"
      :aria-pressed="c.parameter === activeParam"
      @click="analysis.setParam(c.parameter)"
    >
      {{ c.parameter }}
      <!-- red dot when this parameter has failures or flagged sites -->
      <span
        v-if="c.flagged"
        class="inline-flex items-center gap-0.5"
      >
        <span class="h-1.5 w-1.5 rounded-full bg-(--sk-bad)" />
        <span class="text-[9.5px] text-(--sk-bad)">{{ c.flaggedCount }}</span>
      </span>
      <span
        v-else
        class="text-[9.5px] text-(--sk-ink-subtle)"
      >{{ c.measured }}/{{ c.total }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const activeParam = computed(() => props.analysis.activeParam.value)

// One chip per parameter. Coverage + outlier count come from the same overview
// source the panels use, so a chip's red dot agrees with the site table.
const chips = computed(() =>
  props.analysis.paramSummaries.value.map((s) => {
    const ov = props.analysis.overviewFor(s.parameter)
    const flaggedCount = ov.coverage.failed + ov.outlierCount
    return {
      parameter: s.parameter,
      total: ov.coverage.total,
      measured: ov.coverage.measured,
      flagged: flaggedCount > 0,
      flaggedCount
    }
  })
)
</script>
