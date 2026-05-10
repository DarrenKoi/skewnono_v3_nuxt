<template>
  <EbeamComingSoon
    eyebrow="CD-SEM"
    title="Fail 이슈"
    subtitle="장비 Fail 이슈 트래킹 및 분석"
    :fab="fabId"
    icon="i-lucide-triangle-alert"
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
