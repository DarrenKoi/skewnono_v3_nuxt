<template>
  <EbeamSkewvoirView
    tool-label="HV-CD-SEM"
    tool-type="hv-sem"
  />
</template>

<script setup lang="ts">
definePageMeta({
  hideFabSidebar: true
})

const { setToolType } = useNavigation()

setToolType('hv-sem')
</script>
