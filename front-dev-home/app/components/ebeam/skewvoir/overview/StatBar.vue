<template>
  <div class="dashboard-surface flex flex-wrap items-stretch gap-x-5 gap-y-1 rounded-(--sk-r-card) px-3 py-1.5">
    <!-- 측정 성공률 -->
    <div class="flex items-baseline gap-1.5">
      <span class="font-mono text-[9.5px] uppercase tracking-wide text-(--sk-ink-muted)">성공률</span>
      <span
        class="font-mono text-[13px] font-bold tabular-nums"
        :class="cov.failed > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'"
      >{{ cov.measured }}<span class="text-(--sk-ink-subtle)">/{{ cov.total }}</span></span>
      <span
        v-if="cov.failed > 0"
        class="font-mono text-[10px] text-(--sk-bad)"
      >· {{ cov.failed }} 실패</span>
    </div>

    <span class="w-px self-stretch bg-(--sk-border-soft)" />

    <!-- 이상 사이트 -->
    <div class="flex items-baseline gap-1.5">
      <span class="font-mono text-[9.5px] uppercase tracking-wide text-(--sk-ink-muted)">이상</span>
      <span
        v-if="ov.status === 'evaluated'"
        class="font-mono text-[13px] font-bold tabular-nums"
        :class="ov.outlierCount > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'"
      >{{ ov.outlierCount }}</span>
      <span
        v-else
        class="font-mono text-[11px] text-(--sk-ink-subtle)"
      >평가 불가</span>
    </div>

    <span class="w-px self-stretch bg-(--sk-border-soft)" />

    <!-- {param} 평균 -->
    <div class="flex items-baseline gap-1.5">
      <span class="truncate font-mono text-[9.5px] uppercase tracking-wide text-(--sk-ink-muted)">{{ param }} 평균</span>
      <span class="font-mono text-[13px] font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
        {{ summary ? summary.mean.toFixed(2) : '—' }}<span class="text-[10px] text-(--sk-ink-subtle)"> {{ unit }}</span>
      </span>
      <span
        v-if="summary"
        class="font-mono text-[10px] text-(--sk-ink-muted)"
      >· 3σ {{ (summary.std * 3).toFixed(2) }}</span>
    </div>

    <span class="w-px self-stretch bg-(--sk-border-soft)" />

    <!-- 정렬 -->
    <div class="flex min-w-0 items-baseline gap-1.5">
      <span class="font-mono text-[9.5px] uppercase tracking-wide text-(--sk-ink-muted)">정렬</span>
      <span class="font-mono text-[13px] font-bold tabular-nums text-zinc-900 dark:text-zinc-100">{{ align.total }}</span>
      <span class="truncate font-mono text-[10px] text-(--sk-ink-muted)">{{ align.methods.join(' · ') || '—' }}</span>
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
