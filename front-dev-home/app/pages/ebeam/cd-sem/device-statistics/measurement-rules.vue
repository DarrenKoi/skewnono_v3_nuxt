<template>
  <EbeamMeasurementRulesView />
</template>

<script setup lang="ts">
// Measurement-rule editor, colocated with its consumer (device-statistics).
// Fab is chosen inside the view via RuleFabSelector (D15 route decision).
definePageMeta({
  hideFabSidebar: true
})
</script>
