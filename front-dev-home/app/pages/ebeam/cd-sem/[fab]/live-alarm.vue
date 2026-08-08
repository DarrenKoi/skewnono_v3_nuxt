<script setup lang="ts">
// Nuxt reuses this page component across fab param changes by default (R3 ->
// M11 does not remount), which would leave useLiveAlarmFeed polling the fab
// it was first created with. Keying on the full path forces a remount, and
// therefore a fresh feed, whenever the fab segment changes.
definePageMeta({ key: route => route.fullPath })

const { fabs } = useFabRoute('cd-sem')

// The feed's fab list is fixed at creation (see useLiveAlarmFeed's header), so
// the remount above is load-bearing, not an optimization detail. This key says
// so where it can be seen: it makes the view's own fab list the thing that
// forces a fresh feed, so removing the page key above can no longer strand the
// board on a fab the user has left.
const feedKey = computed(() => fabs.value.join(','))
</script>

<template>
  <EbeamLiveAlarmView
    :key="feedKey"
    :fabs="fabs"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>
