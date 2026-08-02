<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('hv-sem')
applyFab(fabName.value)

watch(fabName, (next) => {
  applyFab(next)
})
</script>

<template>
  <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
    <EbeamRecipeSearchView
      :fab="fabName"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
