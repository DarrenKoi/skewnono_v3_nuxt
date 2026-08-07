<template>
  <EbeamRecipeStatusView
    :fabs="fabs"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>

<script setup lang="ts">
const { fabs } = useFabRoute('hv-sem')
</script>
