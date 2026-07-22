// diffNewIds is a relative import (with the .ts extension), not the usual
// '~/' alias every sibling composable uses for utils: this file's pure
// exports (nextDelay, applyPoll) are imported directly by the Node test
// runner, which has no Nuxt build step to resolve '~' — a bare alias
// specifier here would make the whole module unloadable under `node --test`.
import { diffNewIds } from '../utils/liveAlarm.ts'
import type { LiveAlarmEvent, LiveAlarmPayload, FeedStatus } from '~/utils/liveAlarm'

export const POLL_INTERVAL_MS = 15_000
export const POLL_JITTER_MS = 3_000

// Jitter keeps many open tabs from hitting Flask in the same millisecond.
// Exported (rather than calling Math.random inline) so it stays testable.
export const nextDelay = (random: number): number =>
  POLL_INTERVAL_MS + Math.round((random * 2 - 1) * POLL_JITTER_MS)

interface FeedState {
  events: LiveAlarmEvent[]
  ids: string[]
  seenIds: string[]
  newIds: string[]
  feedStatus: FeedStatus
  polledAt: string | null
  serverOffsetMs: number
}

// Pure reducer: one poll response in, next state out. The server ships a
// complete 10-minute board, so this replaces rather than merges — that is
// the whole reason the client carries no accumulation logic.
export const applyPoll = (
  prev: Partial<FeedState>,
  payload: LiveAlarmPayload,
  receivedAtMs: number
): FeedState => {
  const ids = payload.events.map(e => e.id)
  const seenIds = prev.seenIds ?? []
  return {
    events: payload.events,
    ids,
    seenIds,
    newIds: diffNewIds(seenIds.length ? seenIds : (prev.ids ?? []), ids),
    feedStatus: payload.feed_status,
    polledAt: payload.polled_at,
    serverOffsetMs: Date.parse(payload.server_now) - receivedAtMs
  }
}

// The page passes the route-native tool slug (cd-sem / hv-sem), but the
// API path uses the no-hyphen slug (cdsem / hvsem) — same split every
// sibling composable handles (see useFailIssueApi.ts's toolSlug()). There
// is no /ebeam segment on the API path; sibling routes are /api/<slug>/...
const apiSlug = (toolSlug: string): string => toolSlug.replace('-', '')

export const useLiveAlarmFeed = (toolSlug: string, fabName: string) => {
  const key = `live-alarm:${toolSlug}:${fabName}`
  const state = useState<FeedState>(key, () => ({
    events: [], ids: [], seenIds: [], newIds: [],
    feedStatus: 'live', polledAt: null, serverOffsetMs: 0
  }))
  const errorState = useState<string | null>(`${key}:error`, () => null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let consecutiveFailures = 0
  // A fired setTimeout's id is already spent, so stop() clearing `timer`
  // can't reach a callback that is mid-`await poll()` when unmount or a
  // tab hide lands. `active` is the guard the callback re-checks once the
  // await settles — it means "keep the loop going": false while hidden,
  // true again on show, and false for good after unmount (the removed
  // visibilitychange listener is what stops it being flipped back true
  // post-teardown).
  let active = false

  const poll = async () => {
    try {
      const payload = await $fetch<LiveAlarmPayload>(
        `/api/${apiSlug(toolSlug)}/live-alarm`,
        { params: { fab_name: fabName } }
      )
      state.value = applyPoll(state.value, payload, Date.now())
      consecutiveFailures = 0
      errorState.value = null
    } catch {
      // One or two misses are ordinary; only sustained failure is worth
      // showing, and the previous board stays on screen meanwhile.
      consecutiveFailures += 1
      if (consecutiveFailures >= 3) errorState.value = '연결이 불안정합니다'
    }
  }

  const schedule = () => {
    stop()
    timer = setTimeout(async () => {
      await poll()
      // Re-checked after the await, not before: this is the only point
      // that can observe a hide/unmount that landed mid-request, and
      // skipping schedule() here is what actually ends the loop instead
      // of just failing to clear a timer id that already fired.
      if (active) schedule()
    }, nextDelay(Math.random()))
  }

  const stop = () => {
    if (timer !== null) clearTimeout(timer)
    timer = null
  }

  const onVisibility = () => {
    if (document.visibilityState === 'hidden') {
      active = false
      stop()
      return
    }
    // The server holds the whole board, so returning needs no catch-up
    // logic — one ordinary poll restores the full screen.
    active = true
    void poll()
    schedule()
  }

  onMounted(() => {
    active = true
    void poll()
    schedule()
    document.addEventListener('visibilitychange', onVisibility)
  })

  onUnmounted(() => {
    active = false
    stop()
    document.removeEventListener('visibilitychange', onVisibility)
  })

  const markSeen = () => {
    state.value = { ...state.value, seenIds: state.value.ids, newIds: [] }
  }

  return {
    events: computed(() => state.value.events),
    feedStatus: computed(() => state.value.feedStatus),
    polledAt: computed(() => state.value.polledAt),
    serverOffsetMs: computed(() => state.value.serverOffsetMs),
    newIds: computed(() => state.value.newIds),
    // computed, not the raw ref: writable error would let a consumer
    // clear it directly and defeat the consecutive-failures debounce above.
    error: computed(() => errorState.value),
    markSeen
  }
}
