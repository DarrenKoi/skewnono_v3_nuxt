<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('cd-sem')
applyFab(fabName.value)

watch(fabName, (next) => {
  applyFab(next)
})
</script>

<template>
  <EbeamRecipeMeasHistView
    :fab="fabName"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>
