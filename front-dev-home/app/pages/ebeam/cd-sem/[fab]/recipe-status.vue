<template>
  <EbeamRecipeStatusView
    :fab="primaryFab"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>

<script setup lang="ts">
const { primaryFab } = useFabRoute('cd-sem')
</script>
