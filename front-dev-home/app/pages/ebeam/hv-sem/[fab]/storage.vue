<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

setToolType('hv-sem')
setFab(fabId.value as Fab)

watch(fabId, (next) => {
  setFab(next as Fab)
})
</script>

<template>
  <EbeamStorageView
    :fab="fabId"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>
