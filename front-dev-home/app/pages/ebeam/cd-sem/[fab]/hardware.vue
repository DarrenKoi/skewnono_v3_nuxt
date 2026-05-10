<template>
  <EbeamComingSoon
    eyebrow="CD-SEM"
    title="H/W 관리"
    subtitle="장비 하드웨어 구성 및 교체 이력 관리"
    :fab="fabId"
    icon="i-lucide-cpu"
  />
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('cd-sem')
applyFab(fabId.value)

watch(fabId, (next) => {
  applyFab(next)
})
</script>
