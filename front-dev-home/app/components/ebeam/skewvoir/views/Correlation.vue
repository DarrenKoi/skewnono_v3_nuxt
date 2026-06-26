<template>
  <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
    <EbeamSkewvoirPanelFrame
      title="Parameter Correlation"
      meta="param vs param · R²"
      icon="i-lucide-scatter-chart"
      placeholder-height="min-h-80"
    />
    <EbeamSkewvoirPanelFrame
      title="Distribution"
      meta="μ / 3σ / Cpk"
      :toggles="['Hist', 'Box', 'Violin']"
      icon="i-lucide-bar-chart-3"
      placeholder-height="min-h-80"
    />
  </div>
</template>

<script setup lang="ts">
// Correlation & Distribution view — placeholder layout this pass.
</script>
