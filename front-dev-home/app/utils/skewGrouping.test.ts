// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildAdjacency, maximalCliques, type SkewMatrix, type Tier, type Confidence } from './skewGrouping.ts'

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

test('maximalCliques: a TTTM triangle is one clique', () => {
  const adj = [
    [false, true, true],
    [true, false, true],
    [true, true, false],
  ]
  assert.deepEqual(maximalCliques(adj), [[0, 1, 2]])
})

test('maximalCliques: chain A-B-C without A-C yields two pairs, never the triple', () => {
  const adj = [
    [false, true, false],
    [true, false, true],
    [false, true, false],
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '1,2'])
})

test('maximalCliques: isolated vertex is its own clique', () => {
  const adj = [
    [false, true, false],
    [true, false, false],
    [false, false, false],
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '2'])
})

import { groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from './skewGrouping.ts'

const CONF_DIRECT = { tier: 'direct' as Tier, confidence: 'High' as Confidence }

// Two direct cells whose intersection makes {A,B,D} the only triangle at tol=0.05.
const cellsFixture: GroupCell[] = [
  {
    ...CONF_DIRECT,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.02, 0.12, 0.03, 0.18],
        [0.02, 0, 0.10, 0.04, 0.16],
        [0.12, 0.10, 0, 0.11, 0.08],
        [0.03, 0.04, 0.11, 0, 0.15],
        [0.18, 0.16, 0.08, 0.15, 0],
      ],
    },
  },
  {
    ...CONF_DIRECT,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.03, 0.14, 0.04, 0.20],
        [0.03, 0, 0.13, 0.045, 0.19],
        [0.14, 0.13, 0, 0.12, 0.09],
        [0.04, 0.045, 0.12, 0, 0.17],
        [0.20, 0.19, 0.09, 0.17, 0],
      ],
    },
  },
]

test('groupFromCells: intersection yields {A,B,D} as the max clique at 0.05', () => {
  const groups = groupFromCells(cellsFixture, 0.05)
  const top = groups.map(g => g.tools.join(',')).sort()
  assert.ok(top.includes('A,B,D'))
  const abd = groups.find(g => g.tools.join(',') === 'A,B,D')!
  assert.equal(abd.n, 3)
  // weakest pair across both cells for A,B,D = max(A-B,A-D,B-D) = 0.045 (cell 2 B-D)
  assert.equal(abd.weakestPairSkew, 0.045)
  assert.equal(abd.confidence, 'High')
})

test('pickPrimary: larger N wins', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B'], n: 2, weakestPairSkew: 0.01, confidence: 'High', tier: 'direct' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.045, confidence: 'High', tier: 'direct' },
  ]
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,D')
})

test('pickPrimary: equal N breaks on smaller weakest-pair skew, then higher confidence', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B', 'C'], n: 3, weakestPairSkew: 0.04, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.03, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'E'], n: 3, weakestPairSkew: 0.03, confidence: 'High', tier: 'direct' },
  ]
  // tie on N(3); 0.03 beats 0.04; among the two 0.03s, High beats Low
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,E')
})

test('groupFromCells: throws when cells have mismatched tool order', () => {
  const a: GroupCell = {
    tier: 'direct', confidence: 'High',
    matrix: { tools: ['A', 'B'], values: [[0, 0.02], [0.02, 0]] },
  }
  const b: GroupCell = {
    tier: 'direct', confidence: 'High',
    matrix: { tools: ['B', 'A'], values: [[0, 0.02], [0.02, 0]] },
  }
  assert.throws(() => groupFromCells([a, b], 0.05), /tool list/)
})
