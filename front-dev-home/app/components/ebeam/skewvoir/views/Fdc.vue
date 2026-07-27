<template>
  <!-- Single-MSR only. The workbench plots MEASUREMENT ORDER, not time — the MSR
       file carries no per-sequence timestamp — so it has nothing to say about a
       multi-measurement set. That comparison is the Time-Series view. -->
  <EbeamSkewvoirTimeseriesSequenceWorkbench
    v-if="analysis.scope.value === 'single'"
    :analysis="analysis"
  />

  <div
    v-else
    class="dashboard-surface flex h-72 flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 text-center"
  >
    <p class="sk-title">
      FDC 분석
    </p>
    <p class="sk-body">
      측정 하나를 선택하면 sequence별 CD와 dynamic FDC를 함께 볼 수 있습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{
  analysis: SkewvoirAnalysis
}>()
</script>
