import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { diffNewIds, formatElapsed, boardCounts, distinctLotCount } from './liveAlarm.ts'
import { makeAlarmEvent } from './liveAlarm.fixtures.ts'

const event = (id: string, kind: 'align' | 'meas') =>
  makeAlarmEvent({ id, kind, alid: kind === 'align' ? '9006' : '9007' })

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

  it('counts 9007 and 9035 as one meas kind', () => {
    // Many alids, one kind. Counting them separately would split the number
    // an engineer reads as "how much measurement trouble is on this fab".
    const counts = boardCounts([
      makeAlarmEvent({ id: '1', kind: 'meas', alid: '9007' }),
      makeAlarmEvent({ id: '2', kind: 'meas', alid: '9035' })
    ])
    assert.deepEqual(counts, { align: 0, meas: 2 })
  })
})

describe('distinctLotCount', () => {
  it('counts one lot across several alarms once', () => {
    // Four alarms on one lot is a lot problem; four alarms on four lots is a
    // fleet problem. The alarm count alone cannot tell them apart.
    const events = ['1', '2', '3'].map(id => makeAlarmEvent({ id, lot_id: 'NX4201.1' }))
    assert.equal(distinctLotCount(events), 1)
  })

  it('counts distinct lots separately', () => {
    assert.equal(distinctLotCount([
      makeAlarmEvent({ id: '1', lot_id: 'NX4201.1' }),
      makeAlarmEvent({ id: '2', lot_id: 'NX4202.1' })
    ]), 2)
  })

  it('ignores blank lot ids rather than counting them as one unknown lot', () => {
    assert.equal(distinctLotCount([
      makeAlarmEvent({ id: '1', lot_id: '' }),
      makeAlarmEvent({ id: '2', lot_id: '' })
    ]), 0)
  })

  it('returns zero for an empty board', () => {
    assert.equal(distinctLotCount([]), 0)
  })
})
