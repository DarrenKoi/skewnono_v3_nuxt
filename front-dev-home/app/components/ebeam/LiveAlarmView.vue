<script setup lang="ts">
// Shared view for the 라이브 알람 board, one per tool type. Same shape as the
// other Ebeam*View components: the page files stay thin wrappers that only
// resolve the fab and sync navigation state.
import { boardCounts, distinctLotCount, formatElapsed, filterEvents, groupMeasEvents } from '~/utils/liveAlarm'
import type { AlarmFilter } from '~/utils/liveAlarm'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: string
}>()

const fabSlug = computed(() => props.fab.toLowerCase())

const { events, hasLoaded, feedStatus, fetchedAt, unmatchedCount, serverOffsetMs, unseenCount, highlightIds, error, markSeen }
  = useLiveAlarmFeed(props.toolType, props.fab)

const highlightSet = computed(() => new Set(highlightIds.value))
const counts = computed(() => boardCounts(events.value))

const filter = useLiveAlarmFilter()

const FILTERS: { value: AlarmFilter, label: string }[] = [
  { value: 'all', label: '전부 보기' },
  { value: 'align', label: 'Align Fail만' },
  { value: 'meas', label: '측정 실패만' }
]
const FILTER_ORDER: AlarmFilter[] = FILTERS.map(f => f.value)

// The flat list, used by 'all' and 'align'. 'meas' renders groups instead, so
// this stays empty there rather than carrying a list nothing reads.
const visibleEvents = computed(() =>
  filter.value === 'meas' ? [] : filterEvents(events.value, filter.value)
)
const measGroups = computed(() =>
  filter.value === 'meas' ? groupMeasEvents(events.value) : []
)
const hasRows = computed(() => visibleEvents.value.length > 0 || measGroups.value.length > 0)

// Per-mode, because "이 팹은 조용하다" and "이 필터에 해당하는 것이 없다" are
// different facts and a single sentence can only claim one of them.
const emptyMessage = computed(() => ({
  all: '최근 10분간 알람이 없습니다.',
  align: '최근 10분간 Align 실패가 없습니다.',
  meas: '최근 10분간 측정 실패가 없습니다.'
}[filter.value]))

// Roving tabindex, mirroring TimeSeries.vue's lens switch: arrow keys move the
// selection and take focus with it, so the strip is one tab stop, not three.
const filterTabsEl = ref<HTMLElement | null>(null)
const tabId = (value: AlarmFilter) => `live-alarm-filter-${value}`

// One stable id shared by all three tabs' aria-controls, rather than one that
// varies with the selected filter: the board underneath is a single region
// that changes content, not three separate panels, so the two unselected tabs
// would otherwise point at an id nothing claims.
const PANEL_ID = 'live-alarm-board'

const onFilterKeydown = (event: KeyboardEvent): void => {
  const current = FILTER_ORDER.indexOf(filter.value)
  let next = current

  if (event.key === 'ArrowLeft') next = (current - 1 + FILTER_ORDER.length) % FILTER_ORDER.length
  else if (event.key === 'ArrowRight') next = (current + 1) % FILTER_ORDER.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = FILTER_ORDER.length - 1
  else return

  event.preventDefault()
  const target = FILTER_ORDER[next] ?? 'all'
  filter.value = target
  nextTick(() => {
    filterTabsEl.value?.querySelector<HTMLButtonElement>(`#${tabId(target)}`)?.focus()
  })
}

const eyebrow = computed(() => `${props.toolLabel} · ${props.fab}`)

// The last-updated time is shown whether or not there are alarms. An empty
// board means nothing on its own: "quiet fab" and "we know nothing" render
// identically without it.
const sinceLastPoll = computed(() => {
  if (!fetchedAt.value) return '갱신 기록 없음'
  return `${formatElapsed(Date.now() + serverOffsetMs.value - Date.parse(fetchedAt.value))} 갱신`
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

// Alarm counts split by kind, plus the lot count — the alarm count alone reads
// the same whether one lot tripped four tools or four unrelated lots each
// tripped one, and those are different problems.
const metaStats = computed(() => [
  { key: 'align', value: counts.value.align, label: 'Align Fail', tone: 'bad' as const },
  { key: 'meas', value: counts.value.meas, label: '측정 실패', tone: 'warn' as const },
  { key: 'lots', value: distinctLotCount(events.value), label: '관련 lot', tone: 'neutral' as const }
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
      subtitle="최근 10분간 발생한 Align 실패 · 측정 실패"
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

    <!-- Hidden on uncollected fabs: every mode renders the same "not collected"
         sentence there, so the control would offer a choice that does
         nothing — see TimeSeries.vue's lensTabsVisible for the precedent. -->
    <div
      v-if="feedStatus !== 'not_configured'"
      ref="filterTabsEl"
      role="tablist"
      aria-label="알람 종류 필터"
      class="inline-flex w-fit items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
      @keydown="onFilterKeydown"
    >
      <button
        v-for="option in FILTERS"
        :id="tabId(option.value)"
        :key="option.value"
        type="button"
        role="tab"
        :tabindex="filter === option.value ? 0 : -1"
        :aria-selected="filter === option.value"
        :aria-controls="PANEL_ID"
        class="rounded-[6px] px-3 py-1.5 text-xs font-medium transition-colors"
        :class="filter === option.value
          ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="filter = option.value"
      >
        {{ option.label }}
      </button>
    </div>

    <!-- The tablist is conditional, so the panel only claims to be its
         tabpanel while a tab actually exists — a dangling aria-labelledby is
         worse than no relationship at all. The id stays unconditional. -->
    <div
      :id="PANEL_ID"
      class="dashboard-surface overflow-hidden rounded-[var(--sk-r-card)]"
      :role="feedStatus !== 'not_configured' ? 'tabpanel' : undefined"
      :aria-labelledby="feedStatus !== 'not_configured' ? tabId(filter) : undefined"
    >
      <p
        v-if="feedStatus === 'not_configured'"
        class="px-4 py-10 text-center sk-body text-(--sk-ink-muted)"
      >
        {{ fab }} 팹은 아직 라이브 알람 수집 대상이 아닙니다.
      </p>

      <template v-else-if="hasRows">
        <LiveAlarmRow
          v-for="event in visibleEvents"
          :key="event.id"
          :event="event"
          :server-offset-ms="serverOffsetMs"
          :is-new="highlightSet.has(event.id)"
          :tool-slug="toolType"
          :fab="fabSlug"
        />
        <LiveAlarmMeasGroup
          v-for="group in measGroups"
          :key="group.key"
          :group="group"
          :server-offset-ms="serverOffsetMs"
          :highlight-ids="highlightIds"
          :tool-slug="toolType"
          :fab="fabSlug"
        />
      </template>

      <AppLoadingState
        v-else-if="!hasLoaded"
        variant="inline"
        title="라이브 알람 피드를 불러오는 중입니다."
      />

      <p
        v-else
        class="px-4 py-10 text-center sk-body text-(--sk-ink-muted)"
      >
        {{ emptyMessage }}
      </p>
    </div>

    <!-- Reported outside the board, not as a row: these alarms belong to no
         fab, so placing them in this fab's list would be a guess. The count
         is FACILITY-wide (one office call serves every fab in a fac), which
         the wording has to say — sibling fabs all show the same number, and
         "이 팹에서" would be a claim the number cannot support. -->
    <p
      v-if="unmatchedCount > 0"
      class="sk-meta"
    >
      장비 목록에 없어 팹을 특정할 수 없는 알람이 이 설비군 피드에
      {{ unmatchedCount }}건 있습니다.
    </p>
  </div>
</template>
