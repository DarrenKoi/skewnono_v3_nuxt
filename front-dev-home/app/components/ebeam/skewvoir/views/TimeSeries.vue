<template>
  <div class="space-y-3">
    <EbeamSkewvoirPanelFrame
      title="Multi-Measurement Trend"
      meta="mean ± 3σ · SPC limits"
      :toggles="['Xbar', 'EWMA', 'Range']"
      icon="i-lucide-trending-up"
      placeholder-height="min-h-72"
    />
    <EbeamSkewvoirPanelFrame
      title="Sequence Trend"
      meta="by site sequence"
      icon="i-lucide-activity"
      placeholder-height="min-h-56"
    />
  </div>
</template>

<script setup lang="ts">
// Time-Series view — placeholder layout this pass.
</script>
