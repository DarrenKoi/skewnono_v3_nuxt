<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

setToolType('cd-sem')
setFab(fabName.value as Fab)

watch(fabName, (next) => {
  setFab(next as Fab)
})
</script>

<template>
  <div class="space-y-3">
    <EbeamStorageView
      :fab="fabName"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </div>
</template>
