<template>
  <div class="flex h-full min-h-0 flex-col gap-2.5">
    <!-- Top: coverage/outlier/mean/align stats + measurement conditions
         (focus switching lives in the left rail's 비교 세트 for scope=set) -->
    <div class="flex flex-wrap items-stretch gap-2.5">
      <EbeamSkewvoirOverviewStatBar
        class="min-w-0 flex-1"
        :analysis="analysis"
      />
      <EbeamSkewvoirDashboardConditions :analysis="analysis" />
    </div>

    <!-- Parameter navigator — switching it syncs every panel below -->
    <EbeamSkewvoirDashboardParamNav :analysis="analysis" />

    <!-- Inspection zone. On xl the single row spans at least 46rem (the page
         scrolls when the viewport is shorter — the reading panels asked for
         real height); below xl it stacks and the workspace scroll takes over.
         Wafer + Radius + Measurement Points are adjacent so the shared
         focusedSequence selection is visible at once. -->
    <div class="grid min-h-0 flex-1 grid-cols-1 gap-2.5 xl:grid-cols-12 xl:grid-rows-[minmax(46rem,1fr)]">
      <!-- Linked cluster, left: wafer over radius -->
      <div class="flex min-h-0 flex-col gap-2.5 xl:col-span-4">
        <EbeamSkewvoirDashboardWaferMap :analysis="analysis" />
        <EbeamSkewvoirDashboardRadiusPlot
          class="min-h-[18rem] flex-1"
          :analysis="analysis"
        />
      </div>

      <!-- Linked cluster, middle: the per-parameter stat table (backend
           MsrParamSummary) FIRST — readers scan the summary before the point
           list — with measurement points + 이상·실패 filter beneath it -->
      <div class="flex min-h-0 flex-col gap-2.5 xl:col-span-4">
        <EbeamSkewvoirDashboardParamSummary
          class="max-h-96 shrink-0"
          :analysis="analysis"
        />
        <EbeamSkewvoirDashboardMeasurementPoints
          class="min-h-[24rem] flex-1 xl:min-h-0"
          :analysis="analysis"
        />
      </div>

      <!-- Right: SEM image (top, the larger share) over distribution (bottom) -->
      <div class="flex min-h-0 flex-col gap-2.5 xl:col-span-4">
        <EbeamSkewvoirDashboardSemImage
          class="min-h-[26rem] flex-[3] xl:min-h-0"
          :analysis="analysis"
        />
        <EbeamSkewvoirDashboardDistribution
          class="min-h-0 flex-[2]"
          :analysis="analysis"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{ analysis: SkewvoirAnalysis }>()
</script>
