<template>
  <EbeamSkewvoirSearchLanding
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>

<script setup lang="ts">
definePageMeta({
  hideFabSidebar: true
})

const { setToolType } = useNavigation()

setToolType('cd-sem')
</script>
