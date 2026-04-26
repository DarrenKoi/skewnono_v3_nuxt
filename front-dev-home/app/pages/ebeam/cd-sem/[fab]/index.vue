<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
}

setToolType('cd-sem')
applyFab(fabId.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="cd-sem"
    :fab="fabId"
    :title="`CD-SEM - ${fabId}`"
    subtitle="Mocked backend inventory filtered by fab."
  />
</template>
