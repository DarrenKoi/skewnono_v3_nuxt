// diffNewIds is a relative import (with the .ts extension), not the usual
// '~/' alias every sibling composable uses for utils: this file's pure
// exports (nextDelay, applyPoll) are imported directly by the Node test
// runner, which has no Nuxt build step to resolve '~' — a bare alias
// specifier here would make the whole module unloadable under `node --test`.
import { diffNewIds } from '../utils/liveAlarm.ts'
import type { LiveAlarmEvent, LiveAlarmPayload, FeedStatus } from '~/utils/liveAlarm'

export const POLL_INTERVAL_MS = 15_000
export const POLL_JITTER_MS = 3_000
// How long a freshly-arrived row stays highlighted. The spec calls for a
// *brief* highlight ("잠시"), distinct from the unread count, which persists
// until the viewer acknowledges it.
const HIGHLIGHT_MS = 8_000

// Jitter keeps many open tabs from hitting Flask in the same millisecond.
// Exported (rather than calling Math.random inline) so it stays testable.
export const nextDelay = (random: number): number =>
  POLL_INTERVAL_MS + Math.round((random * 2 - 1) * POLL_JITTER_MS)

interface FeedState {
  events: LiveAlarmEvent[]
  ids: string[]
  // Two id sets, deliberately separate:
  //   seenIds    — acknowledged by the viewer (or seeded on first load).
  //   unseenIds  — in the board but not yet acknowledged → drives the title
  //                count, and persists until markSeen().
  //   arrivedIds — new since the PREVIOUS poll → drives the brief row
  //                highlight, which the composable expires on a timer.
  seenIds: string[]
  unseenIds: string[]
  arrivedIds: string[]
  // First successful poll seeds seenIds so the initial board is neither
  // "unread" nor "just arrived" — the viewer opened the page to a board that
  // was already there, not to N alarms that fired the instant they looked.
  initialized: boolean
  feedStatus: FeedStatus
  fetchedAt: string | null
  // Non-zero means the feed carried alarms this build could not attribute to
  // any fab — a roster gap, not a quiet board.
  unmatchedCount: number
  serverOffsetMs: number
}

// Pure reducer: one poll response in, next state out. The server ships a
// complete 20-minute board, so this replaces rather than merges — that is
// the whole reason the client carries no accumulation logic.
export const applyPoll = (
  prev: Partial<FeedState>,
  payload: LiveAlarmPayload,
  receivedAtMs: number
): FeedState => {
  const ids = payload.events.map(e => e.id)
  const initialized = prev.initialized ?? false
  // On the very first poll, treat the whole board as already-seen (seed) so
  // nothing is flagged unread or highlighted; afterwards seenIds only changes
  // via markSeen().
  const seenIds = initialized ? (prev.seenIds ?? []) : ids
  const arrivedIds = initialized ? diffNewIds(prev.ids ?? [], ids) : []
  const seen = new Set(seenIds)
  return {
    events: payload.events,
    ids,
    seenIds,
    unseenIds: ids.filter(id => !seen.has(id)),
    arrivedIds,
    initialized: true,
    feedStatus: payload.feed_status,
    fetchedAt: payload.fetched_at,
    unmatchedCount: payload.unmatched_count,
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
    events: [], ids: [], seenIds: [], unseenIds: [], arrivedIds: [],
    initialized: false, feedStatus: 'live', fetchedAt: null, unmatchedCount: 0,
    serverOffsetMs: 0
  }))
  const errorState = useState<string | null>(`${key}:error`, () => null)
  // Transient row emphasis, kept out of the reducer: a row highlights when it
  // arrives and self-clears on a timer, independent of whether the viewer ever
  // acknowledges (that is the persistent unseen count's job).
  const highlightIds = ref<string[]>([])
  const highlightTimers = new Map<string, ReturnType<typeof setTimeout>>()

  const highlight = (id: string) => {
    if (!highlightIds.value.includes(id)) highlightIds.value = [...highlightIds.value, id]
    const existing = highlightTimers.get(id)
    if (existing) clearTimeout(existing)
    highlightTimers.set(id, setTimeout(() => {
      highlightIds.value = highlightIds.value.filter(x => x !== id)
      highlightTimers.delete(id)
    }, HIGHLIGHT_MS))
  }

  const clearHighlights = () => {
    highlightTimers.forEach(t => clearTimeout(t))
    highlightTimers.clear()
  }

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
      state.value.arrivedIds.forEach(highlight)
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
    clearHighlights()
    document.removeEventListener('visibilitychange', onVisibility)
  })

  // Acknowledge the unread count (title badge). Independent of the row
  // highlight, which fades on its own timer.
  const markSeen = () => {
    state.value = { ...state.value, seenIds: state.value.ids, unseenIds: [] }
  }

  return {
    events: computed(() => state.value.events),
    // Until the first successful poll lands, the badge must not claim "수신 중":
    // that would sit next to a "연결 불안정" error and contradict it.
    hasLoaded: computed(() => state.value.initialized),
    feedStatus: computed(() => state.value.feedStatus),
    fetchedAt: computed(() => state.value.fetchedAt),
    // Reported, never rendered as rows: an unattributable alarm belongs to no
    // fab, so showing it here would put it on the wrong board.
    unmatchedCount: computed(() => state.value.unmatchedCount),
    serverOffsetMs: computed(() => state.value.serverOffsetMs),
    // Persistent unread count (drives the tab title); cleared by markSeen.
    unseenCount: computed(() => state.value.unseenIds.length),
    // Transient per-row emphasis (drives AlarmRow); fades on its own timer.
    highlightIds: computed(() => highlightIds.value),
    // computed, not the raw ref: writable error would let a consumer
    // clear it directly and defeat the consecutive-failures debounce above.
    error: computed(() => errorState.value),
    markSeen
  }
}
