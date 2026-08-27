// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { subsetSkewMatrix, rebaseDeviations, resolveSelection } from './tttmFleetSubset.ts'
import type { SkewMatrix } from './tttmGrouping.ts'

const matrix: SkewMatrix = {
  tools: ['A', 'B', 'C', 'D'],
  values: [
    [0, 0.02, 0.12, null],
    [0.02, 0, 0.10, 0.04],
    [0.12, 0.10, 0, 0.11],
    [null, 0.04, 0.11, 0]
  ]
}

test('subsetSkewMatrix: keeps the wanted tools and their pairwise values', () => {
  const out = subsetSkewMatrix(matrix, ['A', 'C'])
  assert.deepEqual(out.tools, ['A', 'C'])
  assert.deepEqual(out.values, [[0, 0.12], [0.12, 0]])
})

test('subsetSkewMatrix: preserves the matrix ordering, not the argument ordering', () => {
  // Row/column order must keep matching `tools`, so a caller passing ids in a
  // different order cannot transpose the matrix against its own labels.
  const out = subsetSkewMatrix(matrix, ['C', 'A'])
  assert.deepEqual(out.tools, ['A', 'C'])
  assert.equal(out.values[0]![0], 0)
})

test('subsetSkewMatrix: nulls survive the subset as nulls', () => {
  const out = subsetSkewMatrix(matrix, ['A', 'D'])
  assert.deepEqual(out.values, [[0, null], [null, 0]])
})

test('subsetSkewMatrix: an empty selection yields an empty matrix', () => {
  assert.deepEqual(subsetSkewMatrix(matrix, []), { tools: [], values: [] })
})

test('subsetSkewMatrix: unknown ids are ignored rather than inventing rows', () => {
  const out = subsetSkewMatrix(matrix, ['A', 'NOPE'])
  assert.deepEqual(out.tools, ['A'])
  assert.deepEqual(out.values, [[0]])
})

test('resolveSelection: duplicate fleet ids collapse, so the basis has no repeats', () => {
  // sem_list's fleet carries a handful of duplicate eqp_ids, and a repeated id
  // in the basis becomes a repeated row/column in every aligned matrix.
  assert.deepEqual(resolveSelection(['A', 'B', 'A'], null), ['A', 'B'])
  assert.deepEqual(resolveSelection(['A', 'B', 'A'], ['A']), ['A'])
})

const devs = [
  { eqp_id: 'A', deviation: -0.01 },
  { eqp_id: 'B', deviation: 0.01 },
  { eqp_id: 'C', deviation: 0.09 },
  { eqp_id: 'D', deviation: -0.13 }
]

test('rebaseDeviations: the full fleet re-centres on its own median', () => {
  const out = rebaseDeviations(devs, ['A', 'B', 'C', 'D'])
  // median(-0.13, -0.01, 0.01, 0.09) = 0 -> unchanged here.
  assert.deepEqual(out.map(r => r.eqp_id), ['A', 'B', 'C', 'D'])
  assert.ok(Math.abs(out.find(r => r.eqp_id === 'C')!.deviation - 0.09) < 1e-12)
})

test('rebaseDeviations: a subset is re-centred on the SUBSET median', () => {
  // Keeping B, C, D: median(0.01, 0.09, -0.13) = 0.01, so B becomes the centre.
  const out = rebaseDeviations(devs, ['B', 'C', 'D'])
  const by = Object.fromEntries(out.map(r => [r.eqp_id, r.deviation]))
  assert.ok(Math.abs(by.B! - 0) < 1e-12, 'B is the subset median, so it is 0')
  assert.ok(Math.abs(by.C! - 0.08) < 1e-12)
  assert.ok(Math.abs(by.D! - -0.14) < 1e-12)
})

test('rebaseDeviations: the reported deviations always straddle zero', () => {
  // The defining property: re-centring on a median means half the kept tools
  // sit at or below zero. Without it a subset can show every tool on one side,
  // which reads as "the whole group drifted" when nothing drifted at all.
  for (const keep of [['A', 'B'], ['C', 'D'], ['A', 'C', 'D'], ['A', 'B', 'C', 'D']]) {
    const out = rebaseDeviations(devs, keep)
    assert.ok(out.some(r => r.deviation <= 1e-12), `${keep}: nothing at or below 0`)
    assert.ok(out.some(r => r.deviation >= -1e-12), `${keep}: nothing at or above 0`)
  }
})

test('rebaseDeviations: an empty selection yields no rows, not NaN', () => {
  assert.deepEqual(rebaseDeviations(devs, []), [])
  assert.deepEqual(rebaseDeviations(devs, ['NOPE']), [])
})

test('rebaseDeviations: a single kept tool is its own consensus', () => {
  const out = rebaseDeviations(devs, ['C'])
  assert.equal(out.length, 1)
  assert.equal(out[0]!.deviation, 0)
})

test('resolveSelection: null means all, so a fresh user sees the whole fleet', () => {
  assert.deepEqual(resolveSelection(['A', 'B', 'C'], null), ['A', 'B', 'C'])
})

test('resolveSelection: empty means none — what clearing the last group leaves', () => {
  assert.deepEqual(resolveSelection(['A', 'B', 'C'], []), [])
})

test('resolveSelection: a stored selection filters, preserving fleet order', () => {
  assert.deepEqual(resolveSelection(['A', 'B', 'C'], ['C', 'A']), ['A', 'C'])
})

test('resolveSelection: ids that no longer exist are dropped', () => {
  assert.deepEqual(resolveSelection(['A', 'B'], ['A', 'GONE']), ['A'])
})

test('resolveSelection: a wholly stale selection falls back to the fleet', () => {
  // A selection saved for another fab must not blank the screen.
  assert.deepEqual(resolveSelection(['A', 'B'], ['X', 'Y']), ['A', 'B'])
})
