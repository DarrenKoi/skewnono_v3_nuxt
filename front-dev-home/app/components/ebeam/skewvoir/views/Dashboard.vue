<template>
  <div class="grid grid-cols-1 gap-3 xl:grid-cols-12">
    <EbeamSkewvoirDashboardWaferMap
      class="xl:col-span-5"
      :analysis="analysis"
    />
    <EbeamSkewvoirDashboardDataSummary
      class="xl:col-span-7"
      :analysis="analysis"
    />

    <EbeamSkewvoirDashboardRadiusPlot
      class="xl:col-span-5"
      :analysis="analysis"
    />
    <EbeamSkewvoirDashboardSemImage
      class="xl:col-span-4"
      :analysis="analysis"
    />
    <EbeamSkewvoirDashboardDistribution
      class="xl:col-span-3"
      :analysis="analysis"
    />

    <EbeamSkewvoirDashboardMeasurementPoints
      class="xl:col-span-8"
      :analysis="analysis"
    />
    <EbeamSkewvoirDashboardAcquisition
      class="xl:col-span-4"
      :analysis="analysis"
    />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{ analysis: SkewvoirAnalysis }>()
</script>
