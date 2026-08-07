<template>
  <EbeamRecipeStatusView
    :fab="primaryFab"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>

<script setup lang="ts">
const { primaryFab } = useFabRoute('hv-sem')
</script>
