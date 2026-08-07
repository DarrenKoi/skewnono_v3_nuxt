import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { nextDelay, applyPoll, POLL_INTERVAL_MS, POLL_JITTER_MS } from './useLiveAlarmFeed.ts'
import { makeAlarmEvent } from '../utils/liveAlarm.fixtures.ts'
import type { LiveAlarmPayload } from '~/utils/liveAlarm'

const payload = (
  ids: string[],
  serverNowEpochMs: number,
  over: Partial<LiveAlarmPayload> = {}
): LiveAlarmPayload => ({
  fab_names: ['R3'],
  not_configured_fabs: [],
  tool_type: 'cd-sem',
  feed_status: 'live',
  fetched_at: '2026-07-23 10:00:00+09:00',
  covered_since: '2026-07-23 09:40:00+09:00',
  server_now: new Date(serverNowEpochMs).toISOString(),
  board_window_sec: 1200,
  unmatched_count: 0,
  events: ids.map(id => makeAlarmEvent({ id })),
  ...over
})

describe('nextDelay', () => {
  it('sits at the interval when random is centred', () => {
    assert.equal(nextDelay(0.5), POLL_INTERVAL_MS)
  })

  it('never goes below interval minus jitter', () => {
    assert.equal(nextDelay(0), POLL_INTERVAL_MS - POLL_JITTER_MS)
  })

  it('never goes above interval plus jitter', () => {
    assert.equal(nextDelay(1), POLL_INTERVAL_MS + POLL_JITTER_MS)
  })
})

describe('applyPoll', () => {
  it('replaces the list rather than merging', () => {
    // The server sends a complete board every time; merging client-side
    // would resurrect events the server already aged out.
    const first = applyPoll({}, payload(['a', 'b'], 1000), 1000)
    const second = applyPoll(first, payload(['c'], 2000), 2000)
    assert.deepEqual(second.events.map(e => e.id), ['c'])
  })

  it('treats the whole initial board as already-seen, not new', () => {
    // Opening the page to a board that was already there must not flag every
    // row as "just arrived" or leave the tab title showing an unread count.
    const first = applyPoll({}, payload(['a', 'b'], 1000), 1000)
    assert.deepEqual(first.arrivedIds, [])
    assert.deepEqual(first.unseenIds, [])
    assert.equal(first.initialized, true)
  })

  it('flags only genuinely new ids as arrived on later polls', () => {
    const first = applyPoll({}, payload(['a'], 1000), 1000)
    const second = applyPoll(first, payload(['a', 'b'], 2000), 2000)
    assert.deepEqual(second.arrivedIds, ['b'])
    assert.deepEqual(second.unseenIds, ['b'])
  })

  it('keeps unseen ids across an unchanged poll until acknowledged', () => {
    // arrivedIds is per-poll (drives the transient highlight); unseenIds
    // persists (drives the tab-title count) until markSeen reseeds seenIds.
    const first = applyPoll({}, payload(['a'], 1000), 1000)
    const second = applyPoll(first, payload(['a', 'b'], 2000), 2000)
    const third = applyPoll(second, payload(['a', 'b'], 3000), 3000)
    assert.deepEqual(third.arrivedIds, [])
    assert.deepEqual(third.unseenIds, ['b'])
  })

  it('carries not_configured_fabs and per-event fab', () => {
    const state = applyPoll(
      {},
      payload(['a'], 1000, { fab_names: ['R3', 'M16B'], not_configured_fabs: ['M16B'] }),
      1000
    )
    assert.deepEqual(state.notConfiguredFabs, ['M16B'])
    assert.equal(state.events[0]?.fab_name, 'R3')
  })

  it('derives the clock offset from server_now minus receive time', () => {
    const state = applyPoll({}, payload([], 5_000), 3_000)
    assert.equal(state.serverOffsetMs, 2_000)
  })

  it('handles a browser clock running ahead of the server', () => {
    const state = applyPoll({}, payload([], 3_000), 5_000)
    assert.equal(state.serverOffsetMs, -2_000)
  })
})
