<script setup lang="ts">
// Shared view for the 라이브 알람 board, one per tool type. Same shape as the
// other Ebeam*View components: the page files stay thin wrappers that only
// resolve the fab and sync navigation state.
import { boardCounts, formatElapsed } from '~/utils/liveAlarm'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: string
}>()

const fabSlug = computed(() => props.fab.toLowerCase())

const { events, hasLoaded, feedStatus, polledAt, serverOffsetMs, unseenCount, highlightIds, error, markSeen }
  = useLiveAlarmFeed(props.toolType, props.fab)

const highlightSet = computed(() => new Set(highlightIds.value))
const counts = computed(() => boardCounts(events.value))

const eyebrow = computed(() => `${props.toolLabel} · ${props.fab}`)

// The last-updated time is shown whether or not there are alarms. An empty
// board means nothing on its own: "quiet fab" and "we know nothing" render
// identically without it.
const sinceLastPoll = computed(() => {
  if (!polledAt.value) return '갱신 기록 없음'
  return `${formatElapsed(Date.now() + serverOffsetMs.value - Date.parse(polledAt.value))} 갱신`
})

// False until the first successful poll: the badge shows "연결 중" instead of
// "수신 중", so it never contradicts a "연결 불안정" error during startup.
const status = computed(() => {
  if (!hasLoaded.value) return { color: 'neutral' as const, label: '연결 중' }
  return {
    live: { color: 'success' as const, label: '수신 중' },
    stale: { color: 'warning' as const, label: '피드 지연' },
    not_configured: { color: 'neutral' as const, label: '미설정' }
  }[feedStatus.value]
})

const metaStats = computed(() => [
  { key: 'align', value: counts.value.align, label: 'Align Fail', tone: 'bad' as const },
  { key: 'meas', value: counts.value.meas, label: '측정 연속 실패', tone: 'warn' as const }
])

useHead({
  title: computed(() =>
    unseenCount.value
      ? `(${unseenCount.value}) 라이브 알람 · ${props.fab}`
      : `라이브 알람 · ${props.fab}`
  )
})
</script>

<template>
  <div
    class="space-y-3"
    @click="markSeen"
  >
    <EbeamMetaBar
      :eyebrow="eyebrow"
      title="라이브 알람"
      subtitle="최근 10분간 발생한 Align 실패 · 측정 연속 실패"
      :stats="metaStats"
    >
      <template #actions>
        <UBadge
          :color="status.color"
          variant="subtle"
        >
          {{ status.label }}
        </UBadge>
        <EbeamDataFreshness
          label="피드"
          :as-of="sinceLastPoll"
          cadence="15초 주기"
        />
      </template>
    </EbeamMetaBar>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      :description="error"
    />

    <div class="dashboard-surface overflow-hidden rounded-[var(--sk-r-card)]">
      <p
        v-if="feedStatus === 'not_configured'"
        class="px-4 py-10 text-center sk-body text-(--sk-ink-muted)"
      >
        {{ fab }} 팹은 아직 라이브 알람 수집 대상이 아닙니다.
      </p>

      <template v-else-if="events.length">
        <LiveAlarmRow
          v-for="event in events"
          :key="event.id"
          :event="event"
          :server-offset-ms="serverOffsetMs"
          :is-new="highlightSet.has(event.id)"
          :tool-slug="toolType"
          :fab="fabSlug"
        />
      </template>

      <p
        v-else
        class="px-4 py-10 text-center sk-body text-(--sk-ink-muted)"
      >
        최근 10분간 알람이 없습니다.
      </p>
    </div>
  </div>
</template>
