<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('hv-sem')
  setFab('all')
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="hv-sem"
    title="HV-SEM Overview"
    subtitle="Mocked backend inventory loaded from the base e-beam tool-list response."
  />
</template>
