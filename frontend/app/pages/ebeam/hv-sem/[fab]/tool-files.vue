<script setup lang="ts">
const { primaryFab } = useFabRoute('hv-sem')
</script>

<template>
  <EbeamToolFilesView
    :fab="primaryFab"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>
