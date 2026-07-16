<template>
  <div class="flex h-full min-h-0 flex-col gap-2.5">
    <!-- Focus switcher: only renders when the curated set has 2+ members -->
    <EbeamSkewvoirDashboardFocusChipStrip :analysis="analysis" />

    <!-- Top: coverage/outlier/mean/align stats + measurement conditions -->
    <div class="flex flex-wrap items-stretch gap-2.5">
      <EbeamSkewvoirOverviewStatBar
        class="min-w-0 flex-1"
        :analysis="analysis"
      />
      <EbeamSkewvoirDashboardConditions :analysis="analysis" />
    </div>

    <!-- Parameter navigator — switching it syncs every panel below -->
    <EbeamSkewvoirDashboardParamNav :analysis="analysis" />

    <!-- Inspection zone. On xl the single row fills the viewport and each panel
         scrolls internally (no page scroll); below xl it stacks and the
         workspace scroll takes over. Wafer + Radius + Measurement Points are
         adjacent so the shared focusedSequence selection is visible at once. -->
    <div class="grid min-h-0 flex-1 grid-cols-1 gap-2.5 xl:grid-cols-12 xl:grid-rows-[minmax(0,1fr)]">
      <!-- Linked cluster, left: wafer over radius -->
      <div class="flex min-h-0 flex-col gap-2.5 xl:col-span-4">
        <EbeamSkewvoirDashboardWaferMap :analysis="analysis" />
        <EbeamSkewvoirDashboardRadiusPlot
          class="min-h-0 flex-1"
          :analysis="analysis"
        />
      </div>

      <!-- Linked cluster, middle: measurement points + 이상·실패 filter -->
      <EbeamSkewvoirDashboardMeasurementPoints
        class="min-h-0 xl:col-span-4"
        :analysis="analysis"
      />

      <!-- Right: SEM image (top) over distribution (bottom) -->
      <div class="flex min-h-0 flex-col gap-2.5 xl:col-span-4">
        <EbeamSkewvoirDashboardSemImage
          class="min-h-0 flex-1"
          :analysis="analysis"
        />
        <EbeamSkewvoirDashboardDistribution
          class="min-h-0 flex-1"
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
