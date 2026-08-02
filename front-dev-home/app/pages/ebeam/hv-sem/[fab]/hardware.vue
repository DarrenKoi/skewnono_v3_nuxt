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
  <AppAsyncBoundary title="하드웨어 상태 데이터를 불러오는 중입니다.">
    <EbeamHardwareView
      :fab="fabName"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
