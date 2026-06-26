<template>
  <div class="grid grid-cols-1 gap-3 xl:grid-cols-12">
    <EbeamSkewvoirDashboardWaferMap class="xl:col-span-5" />
    <EbeamSkewvoirDashboardDataSummary class="xl:col-span-7" />

    <EbeamSkewvoirDashboardRadiusPlot class="xl:col-span-5" />
    <EbeamSkewvoirDashboardSemImage class="xl:col-span-4" />
    <EbeamSkewvoirDashboardDistribution class="xl:col-span-3" />

    <EbeamSkewvoirDashboardMeasurementPoints class="xl:col-span-8" />
    <EbeamSkewvoirDashboardAcquisition class="xl:col-span-4" />
  </div>
</template>

<script setup lang="ts">
// Single-measurement dashboard — composes its panels from the dashboard/ folder.
// Each panel is its own file so the chart-wiring pass fills one focused leaf at
// a time.
</script>
