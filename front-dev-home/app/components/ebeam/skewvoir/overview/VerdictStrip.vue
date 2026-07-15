<template>
  <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
    <!-- 측정 성공률 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        측정 성공률 · COVERAGE
      </p>
      <p
        class="mt-1 font-mono text-2xl font-bold tabular-nums"
        :class="cov.failed > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'"
      >
        {{ cov.measured }} <span class="text-(--sk-ink-subtle)">/ {{ cov.total }}</span>
      </p>
      <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">
        {{ cov.failed }} 실패 — {{ failPct }}
      </p>
    </div>

    <!-- 이상 사이트 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        이상 사이트 · OUTLIER SITES
      </p>
      <template v-if="ov.status === 'evaluated'">
        <p
          class="mt-1 font-mono text-2xl font-bold tabular-nums"
          :class="ov.outlierCount > 0 ? 'text-(--sk-bad)' : 'text-zinc-900 dark:text-zinc-100'"
        >
          {{ ov.outlierCount }}
        </p>
        <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">
          형제 사이트 대비 · leave-one-out
        </p>
      </template>
      <template v-else>
        <p class="mt-1 font-mono text-lg font-semibold text-(--sk-ink-subtle)">
          평가 불가
        </p>
        <p class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)">
          측정 site 부족
        </p>
      </template>
    </div>

    <!-- {param} 평균 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="truncate font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        {{ param }} 평균 · MEAN
      </p>
      <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
        {{ summary ? summary.mean.toFixed(2) : '—' }} <span class="text-[11px] text-(--sk-ink-subtle)">{{ unit }}</span>
      </p>
      <p
        v-if="summary"
        class="mt-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)"
      >
        3Σ {{ (summary.std * 3).toFixed(2) }} · {{ summary.min.toFixed(1) }} – {{ summary.max.toFixed(1) }}
      </p>
    </div>

    <!-- 정렬 -->
    <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
      <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        정렬 · ALIGNMENT
      </p>
      <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
        {{ align.total }} <span class="text-(--sk-ink-subtle)">/ {{ align.total }}</span>
      </p>
      <p class="mt-0.5 truncate font-mono text-[10.5px] text-(--sk-ink-muted)">
        {{ align.methods.join(' · ') || '—' }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const ov = computed(() => props.analysis.activeOverview.value)
const cov = computed(() => ov.value.coverage)
const failPct = computed(() => cov.value.total ? `${((cov.value.failed / cov.value.total) * 100).toFixed(1)}%` : '—')
const param = computed(() => props.analysis.activeParam.value)
const unit = computed(() => props.analysis.activeUnit.value)
const summary = computed(() => props.analysis.activeSummary.value)
const align = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  const methods = a ? Object.values(a.offset).map(o => o[0]) : []
  return { total: methods.length, methods }
})
</script>
