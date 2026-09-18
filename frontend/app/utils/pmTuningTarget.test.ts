// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tuningTarget } from './pmTuningTarget.ts'
import type { ParameterProfile } from './parameterPca.ts'

// Every column at the monitor-wafer CD, so the action limit is 0.15 nm and a
// tolerance index of 1.0 allows exactly 0.15 nm — chosen so every expected
// number below can be written down by hand.
const CD = 15
const axis = (name: string, tools = 4) => ({ name, median_cd_nm: CD, tools })

// Group = A, B, C. Their P1 mean is (0.00 + 0.06 + 0.12)/3 = 0.06 and their P2
// mean is (0.00 + 0.03 + 0.00)/3 = 0.01. D is the outsider being tuned.
const profile: ParameterProfile = {
  parameters: [axis('P1'), axis('P2')],
  tools: ['A', 'B', 'C', 'D'],
  values: [
    [0.00, 0.00],
    [0.06, 0.03],
    [0.12, 0.00],
    [0.30, -0.05]
  ]
}
const ALL = ['A', 'B', 'C', 'D']
const GROUP = ['A', 'B', 'C']
const near = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-12, `${a} vs ${b}`)
const rowFor = (t: ReturnType<typeof tuningTarget>, name: string) =>
  t!.rows.find(r => r.name === name)!

test('tuningTarget: an outsider aims at the group mean, and delta closes the gap', () => {
  const t = tuningTarget(profile, [], GROUP, ALL, 'D', 1.0)!
  assert.equal(t.source, 'group')
  assert.equal(t.inGroup, false)
  assert.deepEqual(t.unmeasured, [])

  const p1 = rowFor(t, 'P1')
  near(p1.centroidNm, 0.06)
  near(p1.currentNm, 0.30)
  assert.equal(p1.refs, 3)
  // Signed toward the centre: D is high, so the instruction is to come down.
  near(p1.deltaNm, -0.24)

  const p2 = rowFor(t, 'P2')
  near(p2.centroidNm, 0.01)
  near(p2.deltaNm, 0.06)
})

test('tuningTarget: a member aims at the OTHER members — leave-one-out', () => {
  const t = tuningTarget(profile, [], GROUP, ALL, 'B', 1.0)!
  assert.equal(t.inGroup, true)
  // P1 mean of A and C is 0.06 — B is on it, nothing to do. An inclusive mean
  // would say the same here, so P2 is the discriminating case:
  near(rowFor(t, 'P1').deltaNm, 0)
  assert.equal(rowFor(t, 'P1').refs, 2)
  // P2 of A and C is 0.00; B sits at 0.03, so the full −0.03 is the instruction
  // (the inclusive mean of 0.01 would have said −0.02, i.e. (n−1)/n of it).
  near(rowFor(t, 'P2').centroidNm, 0)
  near(rowFor(t, 'P2').deltaNm, -0.03)
})

test('tuningTarget: LOO is a fixed point — after the move the inclusive mean lands there too', () => {
  const t = tuningTarget(profile, [], GROUP, ALL, 'B', 1.0)!
  const p2 = rowFor(t, 'P2')
  const moved = p2.currentNm + p2.deltaNm
  const inclusive = (0.00 + moved + 0.00) / 3
  near(inclusive, p2.centroidNm)
})

test('tuningTarget: with no group, the target is the median of the other compared tools', () => {
  // With an outlier E the MEAN would drift toward it and the median does not.
  const withOutlier: ParameterProfile = {
    parameters: [axis('P1', 5)],
    tools: ['A', 'B', 'C', 'D', 'E'],
    values: [[0.00], [0.06], [0.12], [0.30], [2.00]]
  }
  const t = tuningTarget(withOutlier, [], [], ['A', 'B', 'C', 'D', 'E'], 'D', 1.0)!
  assert.equal(t.source, 'basis')
  assert.equal(t.inGroup, false)
  // median of A, B, C, E = (0.06 + 0.12)/2 = 0.09; the picked tool is excluded.
  near(rowFor(t, 'P1').centroidNm, 0.09)
  assert.equal(rowFor(t, 'P1').refs, 4)
  near(rowFor(t, 'P1').deltaNm, -0.21)
})

test('tuningTarget: the basis fallback honours the comparison, not the whole profile', () => {
  // The profile knows about B and C, but the user deselected them: they must
  // not contribute to the reference.
  const t = tuningTarget(profile, [], [], ['A', 'D'], 'D', 1.0)!
  assert.equal(rowFor(t, 'P1').refs, 1)
  near(rowFor(t, 'P1').centroidNm, 0)
})

test('tuningTarget: the tolerance verdict is per parameter, at that parameter\'s own CD', () => {
  // 0.15 nm allowance at index 1.0; D needs 0.24 on P1 and 0.06 on P2.
  const t = tuningTarget(profile, [], GROUP, ALL, 'D', 1.0)!
  assert.equal(rowFor(t, 'P1').withinTolerance, false)
  assert.equal(rowFor(t, 'P2').withinTolerance, true)
  near(rowFor(t, 'P1').toleranceNm, 0.15)

  // A wide column has a proportionally wider allowance, so the SAME delta can
  // pass on one parameter and fail on another.
  const mixed: ParameterProfile = {
    parameters: [axis('NARROW'), { name: 'WIDE', median_cd_nm: 60, tools: 4 }],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0, 0], [0.2, 0.2]]
  }
  const m = tuningTarget(mixed, [], ['A', 'B'], ['A', 'B', 'D'], 'D', 1.0)!
  assert.equal(rowFor(m, 'NARROW').withinTolerance, false) // 0.2 > 0.15
  assert.equal(rowFor(m, 'WIDE').withinTolerance, true) // 0.2 < 0.60
})

test('tuningTarget: rows are worst-first by CD-relative index, not by raw nm', () => {
  const mixed: ParameterProfile = {
    parameters: [{ name: 'WIDE', median_cd_nm: 60, tools: 3 }, axis('NARROW')],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0, 0], [0.30, 0.20]]
  }
  const t = tuningTarget(mixed, [], ['A', 'B'], ['A', 'B', 'D'], 'D', 1.0)!
  // WIDE needs the larger nm move (0.30 vs 0.20) but NARROW is further past
  // its own limit (1.33x vs 0.50x), so NARROW leads.
  assert.equal(t.rows[0]!.name, 'NARROW')
  assert.equal(t.worst!.name, 'NARROW')
})

test('tuningTarget: selecting parameters narrows the table to the map\'s columns', () => {
  const t = tuningTarget(profile, ['P2'], GROUP, ALL, 'D', 1.0)!
  assert.deepEqual(t.parameters, ['P2'])
  assert.equal(t.rows.length, 1)
  assert.equal(t.rows[0]!.name, 'P2')
  near(t.rows[0]!.centroidNm, 0.01)
})

test('tuningTarget: a hole in the picked tool costs that row only, not the table', () => {
  const holey: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0.06, 0.03], [0.30, null]]
  }
  const t = tuningTarget(holey, [], ['A', 'B'], ['A', 'B', 'D'], 'D', 1.0)!
  assert.deepEqual(t.unmeasured, ['P2'])
  assert.equal(t.rows.length, 1)
  near(rowFor(t, 'P1').deltaNm, -0.27)
})

test('tuningTarget: a hole in a reference drops it from that column only', () => {
  const holey: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'B', 'C', 'D'],
    values: [[0, 0], [0.06, 0.03], [0.12, null], [0.30, -0.05]]
  }
  const t = tuningTarget(holey, [], GROUP, ALL, 'D', 1.0)!
  // C still counts on P1 (mean of 0, 0.06, 0.12 = 0.06)...
  assert.equal(rowFor(t, 'P1').refs, 3)
  near(rowFor(t, 'P1').centroidNm, 0.06)
  // ...and is left out of P2 (mean of 0, 0.03 = 0.015).
  assert.equal(rowFor(t, 'P2').refs, 2)
  near(rowFor(t, 'P2').centroidNm, 0.015)
})

test('tuningTarget: a column no reference measured is named, not rendered as NaN', () => {
  const holey: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'D'],
    values: [[0, null], [0.30, 0.1]]
  }
  const t = tuningTarget(holey, [], [], ['A', 'D'], 'D', 1.0)!
  assert.deepEqual(t.unmeasured, ['P2'])
  assert.equal(t.rows.length, 1)
})

test('tuningTarget: nothing to compute over returns null rather than an empty table', () => {
  assert.equal(tuningTarget(profile, [], GROUP, ALL, null, 1.0), null, 'no tool picked')
  const empty: ParameterProfile = { parameters: [], tools: [], values: [] }
  assert.equal(tuningTarget(empty, [], GROUP, ALL, 'D', 1.0), null, 'no usable column')
  // A column only one tool measured is not usable, and is not a table either.
  const thin: ParameterProfile = {
    parameters: [{ name: 'P1', median_cd_nm: CD, tools: 1 }],
    tools: ['A', 'D'],
    values: [[0], [0.3]]
  }
  assert.equal(tuningTarget(thin, [], ['A'], ['A', 'D'], 'D', 1.0), null, 'single-tool column')
  // But NO GROUP is not "nothing": the basis answers.
  assert.notEqual(tuningTarget(profile, [], [], ALL, 'D', 1.0), null, 'no group still answers')
})
