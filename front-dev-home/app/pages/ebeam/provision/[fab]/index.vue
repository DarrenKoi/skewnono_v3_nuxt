<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab, addRecent } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
  addRecent(next)
}

setToolType('provision')
applyFab(fabId.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="provision"
    :fab="fabId"
    :title="`Provision - ${fabId}`"
    subtitle="Mocked backend inventory filtered by fab."
  />
</template>
