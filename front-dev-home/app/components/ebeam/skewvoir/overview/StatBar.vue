<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-5 gap-y-2 rounded-(--sk-r-card) px-4 py-2.5">
    <!-- 측정 성공률 -->
    <div class="flex flex-col gap-0.5">
      <span class="font-mono text-[11px] tracking-wide text-(--sk-ink-muted)">측정 성공률</span>
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
      <span class="font-mono text-[11px] tracking-wide text-(--sk-ink-muted)">이상 사이트</span>
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

    <!-- {param} 평균 -->
    <div class="flex flex-col gap-0.5">
      <span class="truncate font-mono text-[11px] tracking-wide text-(--sk-ink-muted)">{{ param }} 평균</span>
      <span class="font-mono text-base font-bold tabular-nums text-(--sk-ink)">
        {{ summary ? summary.mean.toFixed(2) : '—' }}<span class="text-xs font-medium text-(--sk-ink-muted)"> {{ unit }}</span>
        <span
          v-if="summary"
          class="text-xs font-medium text-(--sk-ink-muted)"
        > · 3σ <span class="text-(--sk-ink)">{{ (summary.std * 3).toFixed(2) }}</span></span>
      </span>
    </div>

    <span class="h-8 w-px bg-(--sk-border-soft)" />

    <!-- Align -->
    <div class="flex min-w-0 flex-col items-start gap-1">
      <span class="font-mono text-[11px] tracking-wide text-(--sk-ink-muted)">Align</span>
      <span class="truncate font-mono text-base font-bold tabular-nums text-(--sk-ink)">
        {{ align.total }}<span class="text-xs font-medium text-(--sk-ink-muted)"> {{ align.methods.join(' · ') || '—' }}</span>
      </span>
      <EbeamSkewvoirDashboardAlignImages :analysis="analysis" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const ov = computed(() => props.analysis.activeOverview.value)
const cov = computed(() => ov.value.coverage)
const param = computed(() => props.analysis.activeParam.value)
const unit = computed(() => props.analysis.activeUnit.value)
const summary = computed(() => props.analysis.activeSummary.value)
const align = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  const methods = a ? Object.values(a.offset).map(o => o[0]) : []
  return { total: methods.length, methods }
})
</script>
