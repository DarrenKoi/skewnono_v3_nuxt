import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { nextDelay, applyPoll, POLL_INTERVAL_MS, POLL_JITTER_MS } from './useLiveAlarmFeed.ts'
import type { LiveAlarmPayload } from '~/utils/liveAlarm'

const payload = (ids: string[], serverNowEpochMs: number): LiveAlarmPayload => ({
  fab_name: 'R3',
  tool_type: 'cd-sem',
  feed_status: 'live',
  polled_at: '2026-07-23 10:00:00+09:00',
  covered_since: '2026-07-23 09:50:00+09:00',
  server_now: new Date(serverNowEpochMs).toISOString(),
  board_window_sec: 600,
  events: ids.map(id => ({
    id, eqp_id: 'EQ1', alid: '9006', kind: 'align' as const, alarm_name: 'Align Fail',
    occurred_at: '2026-07-23 10:00:00+09:00', occurred_epoch: 1,
    recipe_id: '', operation_desc: '', lot_type_cd: ''
  }))
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
    const first = applyPoll({ ids: [], seenIds: [] }, payload(['a', 'b'], 1000), 1000)
    const second = applyPoll(first, payload(['c'], 2000), 2000)
    assert.deepEqual(second.events.map(e => e.id), ['c'])
  })

  it('reports ids that are new since the previous poll', () => {
    const first = applyPoll({ ids: [], seenIds: ['a'] }, payload(['a'], 1000), 1000)
    const second = applyPoll(first, payload(['a', 'b'], 2000), 2000)
    assert.deepEqual(second.newIds, ['b'])
  })

  it('derives the clock offset from server_now minus receive time', () => {
    const state = applyPoll({ ids: [], seenIds: [] }, payload([], 5_000), 3_000)
    assert.equal(state.serverOffsetMs, 2_000)
  })

  it('handles a browser clock running ahead of the server', () => {
    const state = applyPoll({ ids: [], seenIds: [] }, payload([], 3_000), 5_000)
    assert.equal(state.serverOffsetMs, -2_000)
  })
})
