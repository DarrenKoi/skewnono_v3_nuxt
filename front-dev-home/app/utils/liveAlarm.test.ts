import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  diffNewIds, formatElapsed, boardCounts, distinctLotCount,
  filterEvents, groupMeasEvents
} from './liveAlarm.ts'
import type { LiveAlarmEvent } from './liveAlarm.ts'
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

describe('filterEvents', () => {
  const events = [event('a', 'align'), event('m', 'meas'), event('b', 'align')]

  it('returns every event unchanged for "all"', () => {
    assert.deepEqual(filterEvents(events, 'all'), events)
  })

  it('keeps only align events for "align"', () => {
    assert.deepEqual(filterEvents(events, 'align').map(e => e.id), ['a', 'b'])
  })

  it('keeps only meas events for "meas"', () => {
    assert.deepEqual(filterEvents(events, 'meas').map(e => e.id), ['m'])
  })

  it('returns an empty array rather than throwing on an empty board', () => {
    assert.deepEqual(filterEvents([], 'meas'), [])
  })
})

describe('groupMeasEvents', () => {
  const meas = (over: Partial<LiveAlarmEvent>) =>
    makeAlarmEvent({ kind: 'meas', alid: '9007', ...over })

  it('ignores align events entirely', () => {
    assert.deepEqual(groupMeasEvents([makeAlarmEvent({ kind: 'align' })]), [])
  })

  it('groups by eqp_id and ppid together, not either alone', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'R_A' }),
      meas({ id: '2', eqp_id: 'EQ1', ppid: 'R_B' }),
      meas({ id: '3', eqp_id: 'EQ2', ppid: 'R_A' })
    ])
    assert.deepEqual(groups.map(g => g.key), ['EQ1|R_A', 'EQ1|R_B', 'EQ2|R_A'])
  })

  it('sorts by count descending so the worst offender is first', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'ONCE' }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'TWICE' }),
      meas({ id: '3', eqp_id: 'EQ2', ppid: 'TWICE' })
    ])
    assert.deepEqual(groups.map(g => g.count), [2, 1])
    assert.equal(groups[0]?.key, 'EQ2|TWICE')
  })

  it('breaks a count tie by most recent occurrence', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'OLD', occurred_epoch: 100 }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'NEW', occurred_epoch: 500 })
    ])
    assert.deepEqual(groups.map(g => g.key), ['EQ2|NEW', 'EQ1|OLD'])
  })

  it('orders events inside a group newest first', () => {
    const groups = groupMeasEvents([
      meas({ id: 'old', eqp_id: 'EQ1', ppid: 'R', occurred_epoch: 10 }),
      meas({ id: 'new', eqp_id: 'EQ1', ppid: 'R', occurred_epoch: 90 })
    ])
    assert.deepEqual(groups[0]?.events.map(e => e.id), ['new', 'old'])
    assert.equal(groups[0]?.latestEpoch, 90)
  })

  it('buckets a blank ppid under a label instead of dropping it', () => {
    const groups = groupMeasEvents([meas({ id: '1', eqp_id: 'EQ1', ppid: '' })])
    assert.equal(groups[0]?.key, 'EQ1|')
    assert.equal(groups[0]?.ppidLabel, '(PPID 없음)')
    assert.equal(groups[0]?.count, 1)
  })

  it('counts distinct lots, ignoring blanks', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L1' }),
      meas({ id: '2', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L1' }),
      meas({ id: '3', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L2' }),
      meas({ id: '4', eqp_id: 'EQ1', ppid: 'R', lot_id: '' })
    ])
    assert.equal(groups[0]?.count, 4)
    assert.equal(groups[0]?.lotCount, 2)
  })
})
