<script setup lang="ts">
// Nuxt reuses this page component across fab param changes by default (R3 ->
// M11 does not remount), which would leave useLiveAlarmFeed polling the fab
// it was first created with. Keying on the full path forces a remount, and
// therefore a fresh feed, whenever the fab segment changes.
definePageMeta({ key: route => route.fullPath })

const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <EbeamLiveAlarmView
    :fabs="fabs"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>
