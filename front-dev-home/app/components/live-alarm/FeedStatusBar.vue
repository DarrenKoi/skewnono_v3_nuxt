<script setup lang="ts">
import { formatElapsed, boardCounts } from '~/utils/liveAlarm'
import type { LiveAlarmEvent, FeedStatus } from '~/utils/liveAlarm'

const props = defineProps<{
  feedStatus: FeedStatus
  polledAt: string | null
  serverOffsetMs: number
  events: LiveAlarmEvent[]
}>()

const counts = computed(() => boardCounts(props.events))

// The last-updated time is shown whether or not there are alarms. An empty
// board means nothing on its own: "quiet fab" and "we know nothing" render
// identically without it.
const sinceLastPoll = computed(() => {
  if (!props.polledAt) return null
  const now = Date.now() + props.serverOffsetMs
  return formatElapsed(now - Date.parse(props.polledAt))
})

const tone = computed(() => ({
  live: { color: 'success' as const, label: '수신 중' },
  stale: { color: 'warning' as const, label: '피드 지연' },
  not_configured: { color: 'neutral' as const, label: '미설정' }
}[props.feedStatus]))
</script>

<template>
  <div class="flex flex-wrap items-center gap-3 rounded-lg border border-default px-4 py-3">
    <UBadge
      :color="tone.color"
      variant="subtle"
    >
      {{ tone.label }}
    </UBadge>

    <span
      v-if="sinceLastPoll"
      class="text-sm text-muted"
    >
      마지막 갱신 {{ sinceLastPoll }}
    </span>
    <span
      v-else
      class="text-sm text-muted"
    >갱신 기록 없음</span>

    <span class="ml-auto text-sm">
      Align <strong>{{ counts.align }}</strong>건
      <span class="mx-2 text-muted">·</span>
      측정 <strong>{{ counts.meas }}</strong>건
    </span>
  </div>
</template>
