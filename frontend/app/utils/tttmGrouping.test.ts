// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { alignSkewMatrix, buildAdjacency, maximalCliques, type SkewMatrix, type Tier, type Confidence, groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from './tttmGrouping.ts'
import { effectiveToleranceNm, fractionOfLimit } from './tttmLimits.ts'

const m: SkewMatrix = {
  tools: ['A', 'B', 'C'],
  values: [
    [0, 0.02, 0.12],
    [0.02, 0, 0.10],
    [0.12, 0.10, 0]
  ]
}

test('buildAdjacency: pairs <= tolerance are TTTM, diagonal false, null not TTTM', () => {
  const adj = buildAdjacency(m, 0.05)
  assert.deepEqual(adj, [
    [false, true, false],
    [true, false, false],
    [false, false, false]
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
    [true, true, false]
  ]
  assert.deepEqual(maximalCliques(adj), [[0, 1, 2]])
})

test('maximalCliques: chain A-B-C without A-C yields two pairs, never the triple', () => {
  const adj = [
    [false, true, false],
    [true, false, true],
    [false, true, false]
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '1,2'])
})

test('maximalCliques: isolated vertex is its own clique', () => {
  const adj = [
    [false, true, false],
    [true, false, false],
    [false, false, false]
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '2'])
})

const CONF_DIRECT = { tier: 'direct' as Tier, confidence: 'High' as Confidence }

// Both fixture cells sit at the monitor wafer, where an index of 1x IS 0.15 nm.
// That keeps the nm figures below readable while the engine works in index
// units; the CD-scaling behaviour gets its own fixture further down.
const MONITOR = { ...CONF_DIRECT, cdNm: 15 }
// nm at the monitor wafer -> index
const IDX = (nm: number) => nm / 0.15

// Two direct cells whose intersection makes {A,B,D} the only triangle at tol=0.05.
const cellsFixture: GroupCell[] = [
  {
    ...MONITOR,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.02, 0.12, 0.03, 0.18],
        [0.02, 0, 0.10, 0.04, 0.16],
        [0.12, 0.10, 0, 0.11, 0.08],
        [0.03, 0.04, 0.11, 0, 0.15],
        [0.18, 0.16, 0.08, 0.15, 0]
      ]
    }
  },
  {
    ...MONITOR,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.03, 0.14, 0.04, 0.20],
        [0.03, 0, 0.13, 0.045, 0.19],
        [0.14, 0.13, 0, 0.12, 0.09],
        [0.04, 0.045, 0.12, 0, 0.17],
        [0.20, 0.19, 0.09, 0.17, 0]
      ]
    }
  }
]

test('groupFromCells: intersection yields {A,B,D} as the max clique at 0.05', () => {
  const groups = groupFromCells(cellsFixture, IDX(0.05))
  const top = groups.map(g => g.tools.join(',')).sort()
  assert.ok(top.includes('A,B,D'))
  const abd = groups.find(g => g.tools.join(',') === 'A,B,D')!
  assert.equal(abd.n, 3)
  // weakest pair across both cells for A,B,D = max(A-B,A-D,B-D) = 0.045 (cell 2 B-D)
  assert.equal(abd.weakestPairSkew, 0.045)
  assert.equal(abd.weakestPairIndex, Number((0.045 / 0.15).toFixed(6)))
  assert.equal(abd.confidence, 'High')
})

test('pickPrimary: larger N wins', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B'], n: 2, weakestPairSkew: 0.01, weakestPairIndex: 0.066667, confidence: 'High', tier: 'direct' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.045, weakestPairIndex: 0.300000, confidence: 'High', tier: 'direct' }
  ]
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,D')
})

test('pickPrimary: equal N breaks on smaller weakest-pair index, then higher confidence', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B', 'C'], n: 3, weakestPairSkew: 0.04, weakestPairIndex: 0.266667, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.03, weakestPairIndex: 0.200000, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'E'], n: 3, weakestPairSkew: 0.03, weakestPairIndex: 0.200000, confidence: 'High', tier: 'direct' }
  ]
  // tie on N(3); 0.03 beats 0.04; among the two 0.03s, High beats Low
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,E')
})

test('groupFromCells: throws when cells have mismatched tool order', () => {
  const a: GroupCell = {
    tier: 'direct', confidence: 'High', cdNm: 15,
    matrix: { tools: ['A', 'B'], values: [[0, 0.02], [0.02, 0]] }
  }
  const b: GroupCell = {
    tier: 'direct', confidence: 'High', cdNm: 15,
    matrix: { tools: ['B', 'A'], values: [[0, 0.02], [0.02, 0]] }
  }
  assert.throws(() => groupFromCells([a, b], IDX(0.05)), /tool list/)
})

// --- CD-relative tolerance ---------------------------------------------------

test('fractionOfLimit / effectiveToleranceNm: round-trip at the quoting CD', () => {
  // The knob's nm is quoted at the monitor wafer, so converting there and back
  // must be the identity. If this drifts, every nm on screen is a different
  // number from the one the engine used.
  const index = fractionOfLimit(0.05, 15)
  assert.ok(Math.abs(index - 1 / 3) < 1e-12)
  assert.ok(Math.abs(effectiveToleranceNm(index, 15) - 0.05) < 1e-12)
})

test('effectiveToleranceNm: the same index costs a large-CD cell more nm', () => {
  const index = fractionOfLimit(0.05, 15)
  assert.ok(Math.abs(effectiveToleranceNm(index, 68) - 0.68 / 3) < 1e-12)
  assert.ok(effectiveToleranceNm(index, 68) > effectiveToleranceNm(index, 15))
})

const pair = (skew: number, cdNm: number): GroupCell => ({
  tier: 'direct', confidence: 'High', cdNm,
  matrix: { tools: ['A', 'B'], values: [[0, skew], [skew, 0]] }
})

test('groupFromCells: one skew, two CDs, two different verdicts', () => {
  // 0.15 nm is exactly the action limit on the monitor wafer and a third of it
  // at 68 nm. At a 0.5x knob the small-CD cell must reject the pair and the
  // large-CD cell must accept it — the behaviour an absolute nm tolerance
  // cannot express, and the reason cdNm entered GroupCell.
  const knob = 0.5

  const strict = groupFromCells([pair(0.15, 15)], knob)
  assert.deepEqual(strict.find(g => g.n === 2), undefined, 'must not pair at 15 nm CD')

  const relaxed = groupFromCells([pair(0.15, 68)], knob)
  assert.equal(relaxed.find(g => g.n === 2)?.tools.join(','), 'A,B')
})

test('groupFromCells: intersecting cells judges each against its OWN cd', () => {
  // Same pair, same nm, in two cells at different CDs. The intersection must
  // fail because the 15 nm cell rejects it — not because some averaged CD did.
  const cells = [pair(0.15, 68), pair(0.15, 15)]
  assert.deepEqual(groupFromCells(cells, 0.5).find(g => g.n === 2), undefined)

  // Raise the knob past the strict cell's limit and the intersection opens.
  assert.equal(groupFromCells(cells, 1.01).find(g => g.n === 2)?.tools.join(','), 'A,B')
})

test('groupFromCells: weakestPairSkew is the nm of the worst-INDEX pair', () => {
  // The larger nm (0.30 at CD 68 = 0.44x) is NOT the worse match; the smaller
  // nm (0.10 at CD 15 = 0.67x) is. Reporting max-nm would print 0.300 beside a
  // ranking driven by the 0.100 pair, and the caption would not explain the
  // order it appears in.
  const cells: GroupCell[] = [
    { tier: 'direct', confidence: 'High', cdNm: 68, matrix: { tools: ['A', 'B'], values: [[0, 0.30], [0.30, 0]] } },
    { tier: 'direct', confidence: 'High', cdNm: 15, matrix: { tools: ['A', 'B'], values: [[0, 0.10], [0.10, 0]] } }
  ]
  const ab = groupFromCells(cells, 1)!.find(g => g.n === 2)!
  assert.equal(ab.weakestPairSkew, 0.10)
  assert.equal(ab.weakestPairIndex, Number((0.10 / 0.15).toFixed(6)))
})

test('pickPrimary: equal N ranks on the index, even when nm says otherwise', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B'], n: 2, weakestPairSkew: 0.30, weakestPairIndex: 0.44, confidence: 'High', tier: 'direct' },
    { tools: ['C', 'D'], n: 2, weakestPairSkew: 0.10, weakestPairIndex: 0.67, confidence: 'High', tier: 'direct' }
  ]
  // C,D has the smaller nm and the worse match. The index must win.
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B')
})

const alignFixture: SkewMatrix = {
  tools: ['A', 'B', 'C', 'D'],
  values: [
    [0, 0.02, 0.12, null],
    [0.02, 0, 0.10, 0.04],
    [0.12, 0.10, 0, 0.11],
    [null, 0.04, 0.11, 0]
  ]
}

// --- alignSkewMatrix ---------------------------------------------------------
// The opposite contract to subsetSkewMatrix: the ARGUMENT dictates the order,
// because its job is to put several cells into one basis so `groupFromCells`
// can fold them by positional index.

test('alignSkewMatrix: the argument dictates the order, not the matrix', () => {
  const out = alignSkewMatrix(alignFixture, ['C', 'A'])
  assert.deepEqual(out.tools, ['C', 'A'])
  // Values must travel with their labels, not stay where they were.
  assert.deepEqual(out.values, [[0, 0.12], [0.12, 0]])
})

test('alignSkewMatrix: a tool the matrix lacks becomes an all-null row and column', () => {
  const out = alignSkewMatrix(alignFixture, ['A', 'GHOST', 'B'])
  assert.deepEqual(out.tools, ['A', 'GHOST', 'B'])
  assert.deepEqual(out.values, [
    [0, null, 0.02],
    [null, null, null],
    [0.02, null, 0]
  ])
})

test('alignSkewMatrix: existing nulls survive alignment as nulls', () => {
  const out = alignSkewMatrix(alignFixture, ['A', 'D'])
  assert.deepEqual(out.values, [[0, null], [null, 0]])
})

// The regression this function exists for. Two cells whose tool lists differ —
// contract-legal, since `SkewMatrixBlock` promises only that `tools` indexes
// `values` — used to reach `groupFromCells` unaligned and throw, inside a
// computed consumed during render.
test('alignSkewMatrix: cells with differing tool lists survive groupFromCells', () => {
  const cellA: SkewMatrix = { tools: ['A', 'B'], values: [[0, 0.01], [0.01, 0]] }
  // Same fleet, different order, and one tool this cell never measured.
  const cellB: SkewMatrix = { tools: ['B', 'A'], values: [[0, 0.02], [0.02, 0]] }
  const basis = ['A', 'B', 'C']

  assert.throws(
    () => groupFromCells(
      [
        { tier: 'direct', confidence: 'High', matrix: cellA, cdNm: 15 },
        { tier: 'direct', confidence: 'High', matrix: cellB, cdNm: 15 }
      ],
      1
    ),
    /same tool list/
  )

  const groups = groupFromCells(
    [
      { tier: 'direct', confidence: 'High', matrix: alignSkewMatrix(cellA, basis), cdNm: 15 },
      { tier: 'direct', confidence: 'High', matrix: alignSkewMatrix(cellB, basis), cdNm: 15 }
    ],
    1
  )
  // A and B pass in both cells; C was never measured, so it joins nothing
  // rather than crashing the page.
  const best = groups.find(g => g.n === 2)
  assert.ok(best, 'A and B should still group')
  assert.deepEqual([...best.tools].sort(), ['A', 'B'])
  // C may come back as a singleton clique — that is what "matches nobody"
  // looks like. What must not happen is C being folded into a real group.
  assert.ok(
    !groups.some(g => g.n >= 2 && g.tools.includes('C')),
    'C has no measured pair, so it cannot join a group'
  )
})
