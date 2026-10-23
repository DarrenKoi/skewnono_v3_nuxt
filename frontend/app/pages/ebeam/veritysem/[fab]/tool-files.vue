<script setup lang="ts">
const { fabs } = useFabRoute('veritysem')
</script>

<template>
  <EbeamToolFilesView
    :fabs="fabs"
    tool-label="VeritySEM"
    tool-type="veritysem"
  />
</template>
