<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fabs } = useToolData()

const fabId = computed<Fab>(() => (route.params.fab as string).toUpperCase() as Fab)

const fabConfig = computed(() => {
  return fabs.find(f => f.id === fabId.value) || { id: fabId.value, label: fabId.value }
})

onMounted(() => {
  setToolType('hv-sem')
  setFab(fabId.value as Fab)
})

watch(() => route.params.fab, (newFab) => {
  if (newFab) {
    setFab((newFab as string).toUpperCase() as Fab)
  }
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="hv-sem"
    :fab="fabId"
    :title="`HV-SEM - ${fabConfig.label}`"
    subtitle="Mocked backend inventory filtered by fab."
  />
</template>
