// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildAdjacency, type SkewMatrix } from './skewGrouping.ts'

const m: SkewMatrix = {
  tools: ['A', 'B', 'C'],
  values: [
    [0, 0.02, 0.12],
    [0.02, 0, 0.10],
    [0.12, 0.10, 0],
  ],
}

test('buildAdjacency: pairs <= tolerance are TTTM, diagonal false, null not TTTM', () => {
  const adj = buildAdjacency(m, 0.05)
  assert.deepEqual(adj, [
    [false, true, false],
    [true, false, false],
    [false, false, false],
  ])
})

test('buildAdjacency: null pair is never TTTM', () => {
  const withNull: SkewMatrix = { tools: ['A', 'B'], values: [[0, null], [null, 0]] }
  assert.deepEqual(buildAdjacency(withNull, 0.2), [[false, false], [false, false]])
})
