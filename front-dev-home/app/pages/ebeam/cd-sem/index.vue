<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('cd-sem')
  setFab('all')
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="cd-sem"
    title="CD-SEM Overview"
    subtitle="Mocked backend inventory loaded from the base e-beam tool-list response."
  />
</template>
