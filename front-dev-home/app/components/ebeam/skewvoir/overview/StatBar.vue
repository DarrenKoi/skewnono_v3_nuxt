<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-5 gap-y-2 rounded-(--sk-r-card) px-4 py-2.5">
    <!-- 측정 성공률 -->
    <div class="flex flex-col gap-0.5">
      <span class="sk-label">측정 성공률</span>
      <span
        class="font-mono text-base font-bold tabular-nums"
        :class="cov.failed > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
      >{{ cov.measured }}<span class="text-(--sk-ink-muted)">/{{ cov.total }}</span>
        <span
          v-if="cov.failed > 0"
          class="text-xs font-medium text-(--sk-bad)"
        > · {{ cov.failed }} 실패</span>
      </span>
    </div>

    <span class="h-8 w-px bg-(--sk-border-soft)" />

    <!-- 이상 사이트 -->
    <div class="flex flex-col gap-0.5">
      <span class="sk-label">이상 사이트</span>
      <span
        v-if="ov.status === 'evaluated'"
        class="font-mono text-base font-bold tabular-nums"
        :class="ov.outlierCount > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
      >{{ ov.outlierCount }}</span>
      <span
        v-else
        class="text-sm font-semibold text-(--sk-ink-subtle)"
      >평가 불가</span>
    </div>

    <span class="h-8 w-px bg-(--sk-border-soft)" />

    <!-- Align -->
    <div class="flex min-w-0 flex-col items-start gap-1">
      <span class="sk-label">Align</span>
      <div class="flex min-w-0 items-center gap-2">
        <span class="truncate font-mono text-base font-bold tabular-nums text-(--sk-ink)">
          {{ align.total }}<span class="text-xs font-medium text-(--sk-ink-muted)"> {{ align.methods.join(' · ') || '—' }}</span>
        </span>
        <EbeamSkewvoirDashboardAlignImages
          class="shrink-0"
          :analysis="analysis"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

// The strip states the MEASUREMENT's outcome — how much of it landed, how much
// of it looks wrong, and how it aligned. The parameter's statistics belong to
// the CDU card below it, which is why the mean/3σ cell that used to sit here is
// gone rather than duplicated.
//
// It was not merely redundant: this cell read `activeSummary`, the backend's
// pre-rounded `mean` (3 decimal places), while the card computes from the raw
// rows. On a real measurement that showed as 평균 29.57 here against 29.58 on
// the card — one screen, one word, two numbers. In a metrology tool that costs
// more trust than the cell ever bought.
const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const ov = computed(() => props.analysis.activeOverview.value)
const cov = computed(() => ov.value.coverage)
const align = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  const methods = a ? Object.values(a.offset).map(o => o[0]) : []
  return { total: methods.length, methods }
})
</script>
