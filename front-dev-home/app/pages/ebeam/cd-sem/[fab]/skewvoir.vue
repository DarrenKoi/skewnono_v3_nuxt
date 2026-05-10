<template>
  <EbeamComingSoon
    eyebrow="CD-SEM"
    title="스큐보아"
    subtitle="AI 기반 장비 인사이트 (Skewvoir)"
    :fab="fabId"
    icon="i-lucide-eye"
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
