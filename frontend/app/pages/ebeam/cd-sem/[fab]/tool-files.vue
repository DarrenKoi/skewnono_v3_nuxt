<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <EbeamToolFilesView
    :fabs="fabs"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>
