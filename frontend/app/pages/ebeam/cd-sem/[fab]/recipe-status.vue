<template>
  <EbeamRecipeStatusView
    :fabs="fabs"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>

<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>
