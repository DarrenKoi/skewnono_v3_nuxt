<script setup lang="ts">
// Nuxt reuses this page component across fab param changes by default (R3 ->
// M11 does not remount), which would leave useLiveAlarmFeed polling the fab
// it was first created with. Keying on the full path forces a remount, and
// therefore a fresh feed, whenever the fab segment changes.
definePageMeta({ key: route => route.fullPath })

const route = useRoute()
// The URL fab segment is lowercase (r3); the API and the writer's Redis
// registry use the canonical fab_name (R3), same as storage/index.vue.
const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())
const fabSlug = computed(() => fabName.value.toLowerCase())
const toolSlug = 'cd-sem'

const { events, feedStatus, polledAt, serverOffsetMs, newIds, error, markSeen }
  = useLiveAlarmFeed(toolSlug, fabName.value)

const newIdSet = computed(() => new Set(newIds.value))

useHead({
  title: computed(() =>
    newIds.value.length
      ? `(${newIds.value.length}) 라이브 알람 · ${fabName.value}`
      : `라이브 알람 · ${fabName.value}`
  )
})
</script>

<template>
  <div
    class="space-y-4"
    @click="markSeen"
  >
    <LiveAlarmFeedStatusBar
      :feed-status="feedStatus"
      :polled-at="polledAt"
      :server-offset-ms="serverOffsetMs"
      :events="events"
    />

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      :description="error"
    />

    <UAlert
      v-if="feedStatus === 'not_configured'"
      color="neutral"
      variant="subtle"
      title="라이브 알람 미설정"
      :description="`${fabName} 팹은 아직 라이브 알람 수집 대상이 아닙니다.`"
    />

    <div
      v-else-if="events.length"
      class="rounded-lg border border-default"
    >
      <LiveAlarmRow
        v-for="event in events"
        :key="event.id"
        :event="event"
        :server-offset-ms="serverOffsetMs"
        :is-new="newIdSet.has(event.id)"
        :tool-slug="toolSlug"
        :fab="fabSlug"
      />
    </div>

    <div
      v-else
      class="rounded-lg border border-default px-4 py-10 text-center text-muted"
    >
      최근 10분간 알람이 없습니다.
    </div>
  </div>
</template>
