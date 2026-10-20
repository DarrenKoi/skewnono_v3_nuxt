<script setup lang="ts">
const { fabs } = useFabRoute('hv-sem')
</script>

<template>
  <EbeamToolFilesView
    :fabs="fabs"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>
