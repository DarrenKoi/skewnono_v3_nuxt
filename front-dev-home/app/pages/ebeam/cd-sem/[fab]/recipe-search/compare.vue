<template>
  <AppAsyncBoundary title="비교 데이터를 불러오는 중입니다.">
    <EbeamRecipeCompareView
      :fab="fabName"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>

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
