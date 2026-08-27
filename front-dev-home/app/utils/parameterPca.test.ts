// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parameterPca, type ParameterProfile } from './parameterPca.ts'

// Every column at the monitor-wafer CD, so the action limit is 0.15 nm and the
// index of an offset is offset / 0.15 — chosen so the expected numbers below
// can be written down by hand.
const CD = 15
const axis = (name: string, tools = 3) => ({ name, median_cd_nm: CD, tools })

// A: at consensus. B: a little off on both. C: far off, twice as far on P2.
// Index space — A (0, 0), B (0.2, 0.1), C (1, 2).
const profile: ParameterProfile = {
  parameters: [axis('P1'), axis('P2')],
  tools: ['A', 'B', 'C'],
  values: [
    [0, 0],
    [0.03, 0.015],
    [0.15, 0.30]
  ]
}
const TOOLS = ['A', 'B', 'C']

const point = (r: ReturnType<typeof parameterPca>, eqp: string) => r!.points.find(p => p.eqp_id === eqp)!
const gap = (r: ReturnType<typeof parameterPca>, a: string, b: string) =>
  Math.hypot(point(r, a).x - point(r, b).x, point(r, a).y - point(r, b).y)

test('parameterPca: two columns embed exactly, so map distances are the index-space distances', () => {
  const r = parameterPca(profile, [], TOOLS)!
  assert.equal(r.points.length, 3)
  assert.deepEqual(r.parameters, ['P1', 'P2'])
  assert.ok(Math.abs(gap(r, 'A', 'B') - Math.hypot(0.2, 0.1)) < 1e-9)
  assert.ok(Math.abs(gap(r, 'A', 'C') - Math.hypot(1, 2)) < 1e-9)
  assert.ok(Math.abs(r.explained[0] + r.explained[1] - 1) < 1e-9, 'two components carry everything')
})

test('parameterPca: nearest and score are Chebyshev — the pair\'s worst parameter', () => {
  const r = parameterPca(profile, [], TOOLS)!
  // AB: max(0.2, 0.1) = 0.2. AC: max(1, 2) = 2. BC: max(0.8, 1.9) = 1.9.
  assert.ok(Math.abs(point(r, 'A').nearest - 0.2) < 1e-9)
  assert.ok(Math.abs(point(r, 'B').nearest - 0.2) < 1e-9)
  assert.ok(Math.abs(point(r, 'C').nearest - 1.9) < 1e-9)
  assert.ok(Math.abs(point(r, 'A').score - (0.2 + 2) / 2) < 1e-9)
})

test('parameterPca: perfectly correlated columns put everything on PC1', () => {
  const collinear: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'B', 'C'],
    values: [[0, 0], [0.03, 0.06], [0.09, 0.18]]
  }
  const r = parameterPca(collinear, [], TOOLS)!
  assert.ok(r.explained[0] > 0.999999)
  assert.ok(r.explained[1] < 1e-6)
  for (const p of r.points) assert.ok(Math.abs(p.y) < 1e-6, `${p.eqp_id} is off the line`)
  // The loading of the doubled column is twice the other's, up to normalisation.
  const [l1, l2] = r.loadings
  assert.ok(Math.abs(Math.abs(l2!.pc1) - 2 * Math.abs(l1!.pc1)) < 1e-6)
})

test('parameterPca: selecting narrows the columns, and one column is a line', () => {
  const r = parameterPca(profile, ['P2'], TOOLS)!
  assert.deepEqual(r.parameters, ['P2'])
  assert.deepEqual(r.explained, [1, 0])
  assert.ok(Math.abs(Math.abs(r.loadings[0]!.pc1) - 1) < 1e-9)
  assert.ok(Math.abs(gap(r, 'A', 'C') - 2) < 1e-9)
})

test('parameterPca: a tool with no reading on a used column is detached, not placed at consensus', () => {
  const holey: ParameterProfile = {
    ...profile,
    values: [[0, 0], [0.03, null], [0.15, 0.30]]
  }
  const r = parameterPca(holey, [], TOOLS)!
  assert.deepEqual(r.detached, ['B'])
  assert.deepEqual(r.points.map(p => p.eqp_id), ['A', 'C'])
  // ...but selecting only the column B DID measure brings it back.
  assert.deepEqual(parameterPca(holey, ['P1'], TOOLS)!.detached, [])
})

test('parameterPca: a column one tool measured is skipped rather than detaching everyone', () => {
  const lonely: ParameterProfile = {
    parameters: [axis('P1'), axis('LONE', 1)],
    tools: ['A', 'B', 'C'],
    values: [[0, null], [0.03, null], [0.15, null]]
  }
  const r = parameterPca(lonely, [], TOOLS)!
  assert.deepEqual(r.parameters, ['P1'])
  assert.deepEqual(r.detached, [])
  // And nothing usable at all is null — the caller falls back to the fleet map.
  assert.equal(parameterPca(lonely, ['LONE'], TOOLS), null)
})

test('parameterPca: only the caller\'s tools are placed, and a tool absent from the profile is detached', () => {
  const r = parameterPca(profile, [], ['A', 'C', 'GHOST'])!
  assert.deepEqual(r.points.map(p => p.eqp_id), ['A', 'C'])
  assert.deepEqual(r.detached, ['GHOST'])
})

test('parameterPca: columns at different CDs are compared as fractions of their own limit', () => {
  // Same nm offsets, but P2 is at a 30 nm CD (limit 0.30): its index halves.
  const mixed: ParameterProfile = {
    parameters: [axis('P1'), { name: 'P2', median_cd_nm: 30, tools: 3 }],
    tools: ['A', 'B', 'C'],
    values: [[0, 0], [0.03, 0.03], [0.15, 0.15]]
  }
  const r = parameterPca(mixed, [], TOOLS)!
  // A→C: index (1, 0.5), not (1, 1).
  assert.ok(Math.abs(gap(r, 'A', 'C') - Math.hypot(1, 0.5)) < 1e-9)
  assert.ok(Math.abs(point(r, 'C').nearest - Math.max(0.8, 0.4)) < 1e-9)
})

test('parameterPca: fewer than two placeable tools draws nothing but still says what it used', () => {
  const r = parameterPca(profile, [], ['A'])!
  assert.deepEqual(r.points, [])
  assert.deepEqual(r.parameters, ['P1', 'P2'])
})
