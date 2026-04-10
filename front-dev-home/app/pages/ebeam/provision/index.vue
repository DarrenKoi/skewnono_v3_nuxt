<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('provision')
  setFab('all')
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="provision"
    title="Provision Overview"
    subtitle="Mocked backend inventory loaded from the base e-beam tool-list response."
  />
</template>
