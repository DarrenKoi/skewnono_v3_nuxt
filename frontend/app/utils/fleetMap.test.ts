// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fleetMap } from './fleetMap.ts'
import type { SkewMatrix } from './tttmGrouping.ts'

// Distance between two embedded points, looked up by tool id. MDS coordinates
// are arbitrary up to rotation/reflection/translation, so EVERY assertion about
// an embedding has to be phrased as a distance — comparing raw x/y across two
// runs tests the orientation convention, not the mathematics.
const gap = (r: ReturnType<typeof fleetMap>, a: string, b: string): number => {
  const p = r.points.find(q => q.eqp_id === a)!
  const q = r.points.find(x => x.eqp_id === b)!
  return Math.hypot(p.x - q.x, p.y - q.y)
}

// A 3-4-5 right triangle: exactly representable in 2D, so a correct classical
// MDS reproduces it with zero stress. This is the test that would actually fail
// if the eigendecomposition or the double-centring were wrong.
const triangle: SkewMatrix = {
  tools: ['A', 'B', 'C'],
  values: [
    [0, 3, 4],
    [3, 0, 5],
    [4, 5, 0]
  ]
}

test('fleetMap: an exactly-planar configuration embeds with ~zero stress', () => {
  const r = fleetMap(triangle)
  assert.equal(r.points.length, 3)
  assert.ok(r.stress < 1e-9, `stress ${r.stress} should be ~0`)
})

test('fleetMap: recovers the original pairwise distances', () => {
  const r = fleetMap(triangle)
  assert.ok(Math.abs(gap(r, 'A', 'B') - 3) < 1e-9)
  assert.ok(Math.abs(gap(r, 'A', 'C') - 4) < 1e-9)
  assert.ok(Math.abs(gap(r, 'B', 'C') - 5) < 1e-9)
})

test('fleetMap: stress is a fraction in [0,1] for a non-planar configuration', () => {
  // Four points whose distances cannot be realised in 2D (a regular simplex).
  const simplex: SkewMatrix = {
    tools: ['A', 'B', 'C', 'D'],
    values: [
      [0, 1, 1, 1],
      [1, 0, 1, 1],
      [1, 1, 0, 1],
      [1, 1, 1, 0]
    ]
  }
  const r = fleetMap(simplex)
  assert.ok(r.stress > 0, 'a 3-simplex cannot be flat')
  assert.ok(r.stress <= 1, `stress ${r.stress} must stay a fraction`)
  assert.ok(r.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y)))
})

test('fleetMap: permuting the tool order leaves every pairwise distance intact', () => {
  const permuted: SkewMatrix = {
    tools: ['C', 'A', 'B'],
    values: [
      [0, 4, 5],
      [4, 0, 3],
      [5, 3, 0]
    ]
  }
  const a = fleetMap(triangle)
  const b = fleetMap(permuted)
  for (const [x, y] of [['A', 'B'], ['A', 'C'], ['B', 'C']] as const) {
    assert.ok(
      Math.abs(gap(a, x, y) - gap(b, x, y)) < 1e-9,
      `${x}-${y} moved under permutation`
    )
  }
})

test('fleetMap: a tool with no distances at all is detached, not placed at the origin', () => {
  // EQP05's row is entirely null — the shape cell bc2-X-50-100-e7 actually has.
  const withDetached: SkewMatrix = {
    tools: ['A', 'B', 'C', 'E'],
    values: [
      [0, 3, 4, null],
      [3, 0, 5, null],
      [4, 5, 0, null],
      [null, null, null, 0]
    ]
  }
  const r = fleetMap(withDetached)
  assert.deepEqual(r.detached, ['E'])
  assert.deepEqual(r.points.map(p => p.eqp_id), ['A', 'B', 'C'])
  assert.ok(r.stress < 1e-9, 'dropping the null tool leaves the planar triangle')
})

test('fleetMap: a sporadic null drops only the tool carrying it', () => {
  const sporadic: SkewMatrix = {
    tools: ['A', 'B', 'C', 'D'],
    values: [
      [0, 3, 4, 2],
      [3, 0, 5, null],
      [4, 5, 0, 3],
      [2, null, 3, 0]
    ]
  }
  const r = fleetMap(sporadic)
  assert.equal(r.detached.length, 1)
  assert.equal(r.points.length, 3)
  assert.ok(r.points.every(p => Number.isFinite(p.x)))
})

test('fleetMap: fewer than two placeable tools yields no points', () => {
  const alone: SkewMatrix = { tools: ['A'], values: [[0]] }
  assert.deepEqual(fleetMap(alone), { points: [], detached: ['A'], stress: 0 })
  assert.deepEqual(fleetMap({ tools: [], values: [] }), { points: [], detached: [], stress: 0 })
})

test('fleetMap: score is the mean skew to the other retained tools', () => {
  const r = fleetMap(triangle)
  const a = r.points.find(p => p.eqp_id === 'A')!
  assert.ok(Math.abs(a.score - (3 + 4) / 2) < 1e-9)
  const c = r.points.find(p => p.eqp_id === 'C')!
  assert.ok(Math.abs(c.score - (4 + 5) / 2) < 1e-9)
})

test('fleetMap: nearest is the closest single partner, not the fleet mean', () => {
  const r = fleetMap(triangle)
  const a = r.points.find(p => p.eqp_id === 'A')!
  assert.ok(Math.abs(a.nearest - 3) < 1e-9, 'A closest partner is B at 3')
  const c = r.points.find(p => p.eqp_id === 'C')!
  assert.ok(Math.abs(c.nearest - 4) < 1e-9, 'C closest partner is A at 4')
  // The distinction that matters: comparing `score` against a pairwise
  // tolerance would call A unmatchable at 3.5, when A in fact has a partner
  // well inside it.
  assert.ok(a.score > 3.4 && a.nearest < 3.4)
})

test('fleetMap: an asymmetric matrix is symmetrized rather than producing NaN', () => {
  const asym: SkewMatrix = {
    tools: ['A', 'B', 'C'],
    values: [
      [0, 3, 4],
      [3.2, 0, 5],
      [4, 5, 0]
    ]
  }
  const r = fleetMap(asym)
  assert.ok(r.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y)))
  assert.ok(Math.abs(gap(r, 'A', 'B') - 3.1) < 1e-9, 'A-B should use the mean of 3 and 3.2')
})

test('fleetMap: orientation is deterministic across repeated runs', () => {
  const first = fleetMap(triangle)
  const second = fleetMap(triangle)
  assert.deepEqual(first.points, second.points)
})
