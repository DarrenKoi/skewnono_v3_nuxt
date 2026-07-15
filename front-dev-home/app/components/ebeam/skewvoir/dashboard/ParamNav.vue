<template>
  <div class="flex flex-wrap items-center gap-2 rounded-(--sk-r-card) border border-(--sk-border) bg-(--sk-muted-surface) px-3 py-2">
    <span class="font-mono text-[10px] font-semibold tracking-[0.06em] text-(--sk-ink-muted) uppercase">
      Parameter
    </span>
    <button
      v-for="c in chips"
      :key="c.parameter"
      type="button"
      class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) px-2.5 py-1 font-mono text-xs transition-colors duration-200"
      :class="c.parameter === activeParam
        ? 'bg-(--sk-brand) font-semibold text-(--sk-brand-fg)'
        : 'border border-(--sk-border) bg-(--sk-surface) text-(--sk-ink-muted) hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)'"
      :aria-pressed="c.parameter === activeParam"
      @click="analysis.setParam(c.parameter)"
    >
      {{ c.parameter }}
      <span
        class="text-[11px] tabular-nums"
        :class="c.parameter === activeParam
          ? 'text-(--sk-brand-fg)/80'
          : c.flagged ? 'font-semibold text-(--sk-bad)' : 'text-(--sk-ink-subtle)'"
      >{{ c.flagged ? `● ${c.flaggedCount}` : `${c.measured}/${c.total}` }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const activeParam = computed(() => props.analysis.activeParam.value)

// One chip per parameter. Coverage + outlier count come from the same overview
// source the panels use, so a chip's flag agrees with the site table.
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
