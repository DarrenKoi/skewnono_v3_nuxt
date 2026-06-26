<template>
  <EbeamSkewvoirPanelFrame
    title="Wafer Map"
    meta="slot 13 · 13 sites"
    :toggles="['Cell', 'Dot']"
    icon="i-lucide-grid-3x3"
    placeholder-height="min-h-72"
  />
</template>

<script setup lang="ts">
// Placeholder this pass. The chart-wiring pass renders the ±3σ wafer heat map
// (diverging --sk-scale-low→mid→high) inside the PanelFrame default slot.
</script>
