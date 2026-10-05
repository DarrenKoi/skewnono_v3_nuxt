import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  diffNewIds, formatElapsed, boardCounts, distinctLotCount,
  filterEvents, groupMeasEvents, scopeGroups
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
    assert.deepEqual(groups.map(g => g.key), [
      JSON.stringify(['EQ1', 'R_A']),
      JSON.stringify(['EQ1', 'R_B']),
      JSON.stringify(['EQ2', 'R_A'])
    ])
  })

  it('sorts by count descending so the worst offender is first', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'ONCE' }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'TWICE' }),
      meas({ id: '3', eqp_id: 'EQ2', ppid: 'TWICE' })
    ])
    assert.deepEqual(groups.map(g => g.count), [2, 1])
    assert.equal(groups[0]?.key, JSON.stringify(['EQ2', 'TWICE']))
  })

  it('breaks a count tie by most recent occurrence', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'OLD', occurred_epoch: 100 }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'NEW', occurred_epoch: 500 })
    ])
    assert.deepEqual(groups.map(g => g.key), [
      JSON.stringify(['EQ2', 'NEW']),
      JSON.stringify(['EQ1', 'OLD'])
    ])
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
    assert.equal(groups[0]?.key, JSON.stringify(['EQ1', '']))
    assert.equal(groups[0]?.ppidLabel, '(PPID 없음)')
    assert.equal(groups[0]?.count, 1)
  })

  it('does not collide when a literal separator character sits in different fields', () => {
    // Before the JSON encoding, `${eqp_id}|${ppid}` would merge these two:
    // ("TP01|A", "R") and ("TP01", "A|R") both produced the string "TP01|A|R".
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'TP01|A', ppid: 'R' }),
      meas({ id: '2', eqp_id: 'TP01', ppid: 'A|R' })
    ])
    const keys = groups.map(g => g.key)
    assert.equal(new Set(keys).size, 2)
    assert.equal(groups.length, 2)
    assert.ok(groups.every(g => g.count === 1))
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

describe('scopeGroups', () => {
  // recipe_id and ppid always agree at the office, so the builder sets both.
  const ev = (id: string, over: Partial<LiveAlarmEvent> = {}) =>
    makeAlarmEvent({ id, lot_id: '', ...over, ppid: over.recipe_id ?? '' })

  it('keeps only groups spanning two or more on each axis', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA', lot_id: 'L1' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'RA', lot_id: 'L2' }),
      ev('3', { eqp_id: 'EQ3', recipe_id: 'RB', lot_id: 'L3' }),
      ev('4', { eqp_id: 'EQ3', recipe_id: 'RC', lot_id: 'L3' }),
      ev('5', { eqp_id: 'EQ4', recipe_id: 'RD', lot_id: 'L4' }),
      ev('6', { eqp_id: 'EQ4', recipe_id: 'RD', lot_id: 'L4' })
    ])
    assert.deepEqual(scope.recipeAcrossTools.map(g => g.key), ['recipe:RA'])
    assert.deepEqual(scope.toolAcrossRecipes.map(g => g.key), ['tool:EQ3'])
    assert.deepEqual(scope.lotAcrossTools, [])

    const recipe = scope.recipeAcrossTools[0]
    assert.equal(recipe?.label, 'RA')
    assert.equal(recipe?.eventCount, 2)
    assert.equal(recipe?.toolCount, 2)
    assert.equal(recipe?.recipeCount, 1)
    assert.equal(recipe?.lotCount, 2)
    assert.deepEqual(recipe?.eqpIds, ['EQ1', 'EQ2'])
    assert.deepEqual(recipe?.recipeIds, ['RA'])
    assert.deepEqual(recipe?.lotIds, ['L1', 'L2'])
    assert.equal(scope.toolAcrossRecipes[0]?.recipeCount, 2)
  })

  it('sends a blank ppid/recipe and a blank lot to omitted instead of grouping them', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: '', lot_id: '' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: '', lot_id: '' }),
      ev('3', { eqp_id: 'EQ3', recipe_id: 'RA', lot_id: 'L1' })
    ])
    assert.deepEqual(scope.recipeAcrossTools, [])
    assert.deepEqual(scope.lotAcrossTools, [])
    assert.deepEqual(scope.omitted, { blankRecipe: 2, blankLot: 2 })
  })

  it('does not count a blank recipe towards a tool spanning several recipes', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA' }),
      ev('2', { eqp_id: 'EQ1', recipe_id: '' })
    ])
    assert.deepEqual(scope.toolAcrossRecipes, [])
  })

  it('skips a blank eqp_id on the tool axis', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: '', recipe_id: 'RA' }),
      ev('2', { eqp_id: '', recipe_id: 'RB' })
    ])
    assert.deepEqual(scope.toolAcrossRecipes, [])
  })

  it('counts align and meas together and splits them in kinds', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA', kind: 'align', alid: '9006' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'RA', kind: 'meas', alid: '9007' }),
      ev('3', { eqp_id: 'EQ2', recipe_id: 'RA', kind: 'meas', alid: '9035' })
    ])
    const group = scope.recipeAcrossTools[0]
    assert.equal(group?.eventCount, 3)
    assert.deepEqual(group?.kinds, { align: 1, meas: 2 })
  })

  it('counts alarms per alid', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA', kind: 'meas', alid: '9007' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'RA', kind: 'meas', alid: '9007' }),
      ev('3', { eqp_id: 'EQ2', recipe_id: 'RA', kind: 'meas', alid: '9035' })
    ])
    assert.deepEqual(scope.recipeAcrossTools[0]?.alids, { 9007: 2, 9035: 1 })
  })

  it('reports the first and last epoch of the group', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA', occurred_epoch: 500 }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'RA', occurred_epoch: 100 }),
      ev('3', { eqp_id: 'EQ3', recipe_id: 'RA', occurred_epoch: 900 })
    ])
    assert.equal(scope.recipeAcrossTools[0]?.firstEpoch, 100)
    assert.equal(scope.recipeAcrossTools[0]?.lastEpoch, 900)
  })

  it('sorts by span, then event count, then recency, then label', () => {
    const scope = scopeGroups([
      // WIDE: three tools.
      ev('1', { eqp_id: 'EQ1', recipe_id: 'WIDE' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'WIDE' }),
      ev('3', { eqp_id: 'EQ3', recipe_id: 'WIDE' }),
      // BUSY: two tools, three events.
      ev('4', { eqp_id: 'EQ1', recipe_id: 'BUSY' }),
      ev('5', { eqp_id: 'EQ2', recipe_id: 'BUSY' }),
      ev('6', { eqp_id: 'EQ2', recipe_id: 'BUSY' }),
      // NEW: two tools, two events, the most recent.
      ev('7', { eqp_id: 'EQ1', recipe_id: 'NEW', occurred_epoch: 50 }),
      ev('8', { eqp_id: 'EQ2', recipe_id: 'NEW', occurred_epoch: 60 }),
      // B and A: identical but for the label.
      ev('9', { eqp_id: 'EQ1', recipe_id: 'B' }),
      ev('10', { eqp_id: 'EQ2', recipe_id: 'B' }),
      ev('11', { eqp_id: 'EQ1', recipe_id: 'A' }),
      ev('12', { eqp_id: 'EQ2', recipe_id: 'A' })
    ])
    assert.deepEqual(
      scope.recipeAcrossTools.map(g => g.label),
      ['WIDE', 'BUSY', 'NEW', 'A', 'B']
    )
  })

  it('ranks the tool axis by recipe count', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA' }),
      ev('2', { eqp_id: 'EQ1', recipe_id: 'RB' }),
      ev('3', { eqp_id: 'EQ1', recipe_id: 'RB' }),
      ev('4', { eqp_id: 'EQ2', recipe_id: 'RA' }),
      ev('5', { eqp_id: 'EQ2', recipe_id: 'RB' }),
      ev('6', { eqp_id: 'EQ2', recipe_id: 'RC' })
    ])
    assert.deepEqual(scope.toolAcrossRecipes.map(g => g.label), ['EQ2', 'EQ1'])
  })

  it('finds one lot seen on several tools', () => {
    const scope = scopeGroups([
      ev('1', { eqp_id: 'EQ1', recipe_id: 'RA', lot_id: 'L1' }),
      ev('2', { eqp_id: 'EQ2', recipe_id: 'RB', lot_id: 'L1' }),
      ev('3', { eqp_id: 'EQ3', recipe_id: 'RC', lot_id: 'L1' }),
      ev('4', { eqp_id: 'EQ4', recipe_id: 'RD', lot_id: 'L2' })
    ])
    assert.deepEqual(scope.lotAcrossTools.map(g => g.key), ['lot:L1'])
    assert.equal(scope.lotAcrossTools[0]?.toolCount, 3)
    assert.equal(scope.lotAcrossTools[0]?.recipeCount, 3)
    assert.equal(scope.lotAcrossTools[0]?.lotCount, 1)
  })

  it('returns empty lists and zero omissions for an empty board', () => {
    assert.deepEqual(scopeGroups([]), {
      recipeAcrossTools: [],
      toolAcrossRecipes: [],
      lotAcrossTools: [],
      omitted: { blankRecipe: 0, blankLot: 0 }
    })
  })
})
