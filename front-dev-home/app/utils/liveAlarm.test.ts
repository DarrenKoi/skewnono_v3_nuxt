import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { diffNewIds, formatElapsed, boardCounts } from './liveAlarm.ts'
import type { LiveAlarmEvent } from './liveAlarm.ts'

const event = (id: string, kind: 'align' | 'meas'): LiveAlarmEvent => ({
  id, eqp_id: 'EQ1', alid: kind === 'align' ? '9006' : '9100', kind,
  alarm_name: 'x', occurred_at: '2026-07-23 10:00:00+09:00', occurred_epoch: 1,
  recipe_id: '', operation_desc: '', lot_type_cd: ''
})

describe('diffNewIds', () => {
  it('returns ids present in next but not prev', () => {
    assert.deepEqual(diffNewIds(['a'], ['a', 'b']), ['b'])
  })

  it('returns nothing when the sets match', () => {
    assert.deepEqual(diffNewIds(['a', 'b'], ['b', 'a']), [])
  })

  it('ignores ids that disappeared', () => {
    assert.deepEqual(diffNewIds(['a', 'b'], ['a']), [])
  })

  it('treats the first load as all-new', () => {
    assert.deepEqual(diffNewIds([], ['a', 'b']), ['a', 'b'])
  })
})

describe('formatElapsed', () => {
  it('shows seconds under a minute', () => {
    assert.equal(formatElapsed(45_000), '45초 전')
  })

  it('shows minutes past a minute', () => {
    assert.equal(formatElapsed(185_000), '3분 전')
  })

  it('shows hours past an hour', () => {
    assert.equal(formatElapsed(7_400_000), '2시간 전')
  })

  it('clamps negatives to now instead of rendering "-2분 전"', () => {
    // A clock still settling must never produce a negative elapsed label.
    assert.equal(formatElapsed(-5_000), '방금')
  })
})

describe('boardCounts', () => {
  it('counts each kind', () => {
    const counts = boardCounts([event('1', 'align'), event('2', 'meas'), event('3', 'align')])
    assert.deepEqual(counts, { align: 2, meas: 1 })
  })

  it('returns zeroes for an empty board', () => {
    assert.deepEqual(boardCounts([]), { align: 0, meas: 0 })
  })
})
