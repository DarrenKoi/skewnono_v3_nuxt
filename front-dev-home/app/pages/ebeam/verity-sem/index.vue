<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('verity-sem')
  setFab('all')
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="verity-sem"
    title="VeritySEM Overview"
    subtitle="Mocked backend inventory loaded from the base e-beam tool-list response."
  />
</template>
