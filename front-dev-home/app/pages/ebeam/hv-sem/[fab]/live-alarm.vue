<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

// Nuxt reuses this page component across fab param changes by default (R3 ->
// M11 does not remount), which would leave useLiveAlarmFeed polling the fab
// it was first created with. Keying on the full path forces a remount, and
// therefore a fresh feed, whenever the fab segment changes.
definePageMeta({ key: route => route.fullPath })

const route = useRoute()
const { setToolType, setFab } = useNavigation()

// The URL fab segment is lowercase (r3); the API and the writer's Redis
// registry use the canonical fab_name (R3), same as storage/index.vue.
const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

// No watch on fabName here, unlike the sibling pages: definePageMeta's key
// remounts this page on every fab change, so setup runs again with the new fab.
setToolType('hv-sem')
setFab(fabName.value as Fab)
</script>

<template>
  <EbeamLiveAlarmView
    :fab="fabName"
    tool-label="HV-SEM"
    tool-type="hv-sem"
  />
</template>
