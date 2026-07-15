<template>
  <div class="space-y-3">
    <!-- Verdict strip — follows the active parameter -->
    <EbeamSkewvoirOverviewVerdictStrip :analysis="analysis" />

    <!-- Parameter navigator — the per-parameter summary; pick the active param -->
    <EbeamSkewvoirDashboardDataSummary :analysis="analysis" />

    <!-- Inspection zone — all linked by focusedSequence -->
    <div class="grid grid-cols-1 gap-3 xl:grid-cols-12">
      <EbeamSkewvoirDashboardWaferMap
        class="xl:col-span-5"
        :analysis="analysis"
      />

      <div class="flex flex-col gap-3 xl:col-span-7">
        <EbeamSkewvoirOverviewSiteVerdicts :analysis="analysis" />
        <EbeamSkewvoirDashboardDistribution :analysis="analysis" />
      </div>

      <EbeamSkewvoirDashboardRadiusPlot
        class="xl:col-span-5"
        :analysis="analysis"
      />
      <EbeamSkewvoirDashboardMeasurementPoints
        class="xl:col-span-4"
        :analysis="analysis"
      />
      <EbeamSkewvoirDashboardSemImage
        class="xl:col-span-3"
        :analysis="analysis"
      />

      <EbeamSkewvoirDashboardAcquisition
        class="xl:col-span-12"
        :analysis="analysis"
      />
    </div>

    <!-- Wafer map legend -->
    <p class="flex flex-wrap items-center gap-3 px-1 font-mono text-[10.5px] text-(--sk-ink-muted)">
      <span class="inline-flex items-center gap-1"><span
        class="h-2.5 w-2.5 rounded-full"
        style="background:#5C86AE"
      /> 낮음</span>
      <span class="inline-flex items-center gap-1"><span
        class="h-2.5 w-2.5 rounded-full"
        style="background:#C75A3C"
      /> 높음</span>
      <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">✕</span> 측정 실패 (cd_value: null)</span>
      <span class="inline-flex items-center gap-1"><span class="text-(--sk-bad)">◎</span> 이상 사이트</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{ analysis: SkewvoirAnalysis }>()
</script>
