<script setup lang="ts">
const { fabs } = useFabRoute('provision')
</script>

<template>
  <EbeamToolFilesView
    :fabs="fabs"
    tool-label="Provision"
    tool-type="provision"
  />
</template>
