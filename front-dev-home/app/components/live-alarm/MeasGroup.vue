<script setup lang="ts">
import { formatElapsed } from '~/utils/liveAlarm'
import type { MeasGroupItem } from '~/utils/liveAlarm'

const props = defineProps<{
  group: MeasGroupItem
  serverOffsetMs: number
  highlightIds: string[]
  toolSlug: string
  fab: string
  fabBadge?: string
}>()

// Component-local, and it survives polling: the parent keys the v-for by
// group.key, which is derived from (eqp_id, ppid) rather than from an index,
// so Vue reuses this instance instead of remounting it every 15 seconds.
const expanded = ref(false)

const highlightSet = computed(() => new Set(props.highlightIds))

// A one-event group renders as a bare row — a header, a chevron and a "1건"
// badge around a single alarm is furniture, not information.
const isSingleton = computed(() => props.group.count === 1)

// Lifted from the row to the header on purpose. The row-level highlight fires
// into collapsed (invisible) DOM, so without this the arrival of a new alarm
// is silent exactly when the pile-up is worth noticing.
const hasNew = computed(() =>
  props.group.events.some(event => highlightSet.value.has(event.id))
)

const elapsed = computed(() =>
  formatElapsed(Date.now() + props.serverOffsetMs - props.group.latestEpoch * 1000)
)
</script>

<template>
  <LiveAlarmRow
    v-if="isSingleton && group.events[0]"
    :event="group.events[0]"
    :server-offset-ms="serverOffsetMs"
    :is-new="highlightSet.has(group.events[0].id)"
    :tool-slug="toolSlug"
    :fab="fab"
    :fab-badge="fabBadge"
  />

  <div
    v-else
    class="border-b border-default last:border-b-0"
  >
    <button
      type="button"
      class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition-colors duration-1000"
      :class="hasNew ? 'bg-(--sk-accent-tint)' : 'bg-transparent'"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <UIcon
        :name="expanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
        class="size-4 shrink-0 text-(--sk-ink-muted)"
      />

      <span class="text-lg font-semibold tracking-tight">{{ group.eqpId }}</span>
      <span
        v-if="fabBadge"
        class="inline-flex items-center rounded bg-zinc-100 px-1.5 py-0.5 font-sans text-[9px] font-semibold text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-300"
      >
        {{ fabBadge }}
      </span>
      <span class="font-mono text-sm text-(--sk-ink-muted)">{{ group.ppidLabel }}</span>

      <!-- The count is the argument this whole view exists to make, so it is
           the loudest thing in the header. -->
      <span class="text-lg font-semibold text-(--sk-warn)">{{ group.count }}건</span>

      <span class="text-sm text-muted">{{ elapsed }}</span>
      <span class="ml-auto sk-meta">관련 lot {{ group.lotCount }}</span>
    </button>

    <div v-if="expanded">
      <LiveAlarmRow
        v-for="event in group.events"
        :key="event.id"
        :event="event"
        :server-offset-ms="serverOffsetMs"
        :is-new="highlightSet.has(event.id)"
        :tool-slug="toolSlug"
        :fab="fab"
        :fab-badge="fabBadge"
      />
    </div>
  </div>
</template>
