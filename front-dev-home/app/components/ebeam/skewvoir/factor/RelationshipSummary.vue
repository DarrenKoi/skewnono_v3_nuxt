<template>
  <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
    <div class="flex flex-wrap items-stretch gap-2">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="min-w-[5.5rem] flex-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2"
      >
        <p class="sk-eyebrow">
          {{ stat.label }}
        </p>
        <p
          class="mt-0.5 font-mono text-[15px] font-semibold tabular-nums"
          :class="stat.muted ? 'text-(--sk-ink-subtle)' : 'text-(--sk-ink)'"
        >
          {{ stat.value }}
        </p>
      </div>
    </div>

    <!-- Readiness banner: 평가 불가 reason, or the honest caveats when ready. -->
    <div
      v-if="result.readiness === 'unavailable'"
      class="mt-2 flex items-center gap-1.5 rounded-(--sk-r-nav) bg-(--sk-chip-bg) px-2.5 py-1.5 text-[12px] text-(--sk-ink-subtle)"
    >
      <UIcon
        name="i-lucide-circle-slash"
        class="h-3.5 w-3.5 shrink-0"
      />
      <span>{{ result.reason ?? '평가 불가' }}</span>
    </div>

    <div class="mt-2 flex flex-wrap gap-1.5">
      <!-- ALWAYS shown: correlation is not causation. -->
      <span class="inline-flex items-center gap-1 rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 text-[11px] font-medium text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-info"
          class="h-3 w-3"
        />
        연관이며 원인 증명이 아님
      </span>
      <!-- CD↔FDC same-MSR+sequence join meta. -->
      <span
        v-if="result.sameMsrSequenceJoin"
        class="inline-flex items-center gap-1 rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 text-[11px] font-medium text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-link-2"
          class="h-3 w-3"
        />
        동일 MSR · sequence 조인
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { RelationshipResult } from '~/utils/skewvoirAnalysis/relationships'

const props = defineProps<{ result: RelationshipResult }>()

const fmt = (v: number | null) => (v == null ? '—' : v.toFixed(3))

const stats = computed(() => [
  { label: 'Pearson r', value: fmt(props.result.pearson), muted: props.result.pearson == null },
  { label: 'Spearman ρ', value: fmt(props.result.spearman), muted: props.result.spearman == null },
  { label: '짝 N', value: String(props.result.pairN), muted: props.result.pairN === 0 },
  { label: '누락 N', value: String(props.result.missingN), muted: props.result.missingN === 0 }
])
</script>
