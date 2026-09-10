// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tuningTarget } from './pmTuningTarget.ts'
import { parameterPca, type ParameterProfile } from './parameterPca.ts'

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
const GROUP = ['A', 'B', 'C']
const rowFor = (t: ReturnType<typeof tuningTarget>, name: string) =>
  t!.rows.find(r => r.name === name)!

test('tuningTarget: the target is the group centroid, and delta is what closes the gap', () => {
  const t = tuningTarget(profile, [], GROUP, 'D', 1.0)!
  assert.equal(t.members, 3)
  assert.equal(t.inGroup, false)
  assert.equal(t.placed, true)

  const p1 = rowFor(t, 'P1')
  assert.ok(Math.abs(p1.centroidNm - 0.06) < 1e-12)
  assert.ok(Math.abs(p1.currentNm - 0.30) < 1e-12)
  // Signed toward the centre: D is high, so the instruction is to come down.
  assert.ok(Math.abs(p1.deltaNm - -0.24) < 1e-12)

  const p2 = rowFor(t, 'P2')
  assert.ok(Math.abs(p2.centroidNm - 0.01) < 1e-12)
  assert.ok(Math.abs(p2.deltaNm - 0.06) < 1e-12)
})

test('tuningTarget: the centroid IS the map ring centre — the whole claim of the card', () => {
  // The invariant that lets the table say "aim at the point the 배치도 draws":
  // PCA centres and projects, both linear, so the mean of the members' drawn
  // coordinates must equal the projection of the parameter-space centroid.
  //
  // Checked through parameterPca itself rather than re-deriving the projection
  // here, so a change to either file that breaks the agreement fails this test.
  const tools = ['A', 'B', 'C', 'D']
  const pca = parameterPca(profile, [], tools)!
  const t = tuningTarget(profile, [], GROUP, 'D', 1.0)!

  const members = GROUP.map(eqp => pca.points.find(p => p.eqp_id === eqp)!)
  const ringX = members.reduce((s, p) => s + p.x, 0) / members.length
  const ringY = members.reduce((s, p) => s + p.y, 0) / members.length

  // Project the table's centroid the same way parameterPca projects a tool:
  // place a synthetic tool AT the centroid and read where the map puts it.
  const withCentroid: ParameterProfile = {
    parameters: profile.parameters,
    tools: [...profile.tools, 'CENTROID'],
    values: [
      ...profile.values,
      [rowFor(t, 'P1').centroidNm, rowFor(t, 'P2').centroidNm]
    ]
  }
  // Same tool set, so the same column means and the same eigenvectors: only
  // the extra point is added, and it is added AFTER the basis is fixed by
  // asking for it in a second run over the original tools plus one.
  const probe = parameterPca(withCentroid, [], tools)!
  const basis = new Map(probe.points.map(p => [p.eqp_id, p]))
  const shiftX = basis.get('A')!.x - pca.points.find(p => p.eqp_id === 'A')!.x
  const shiftY = basis.get('A')!.y - pca.points.find(p => p.eqp_id === 'A')!.y
  assert.ok(Math.abs(shiftX) < 1e-9 && Math.abs(shiftY) < 1e-9, 'basis must be unchanged')

  const placed = parameterPca(withCentroid, [], [...tools, 'CENTROID'])!
  const centroidPoint = placed.points.find(p => p.eqp_id === 'CENTROID')!
  // The added point shifts the column means, so compare the centroid against
  // the ring computed in the SAME run rather than across runs.
  const sameRun = GROUP.map(eqp => placed.points.find(p => p.eqp_id === eqp)!)
  const sameRingX = sameRun.reduce((s, p) => s + p.x, 0) / sameRun.length
  const sameRingY = sameRun.reduce((s, p) => s + p.y, 0) / sameRun.length

  assert.ok(Math.abs(centroidPoint.x - sameRingX) < 1e-9, `x ${centroidPoint.x} vs ${sameRingX}`)
  assert.ok(Math.abs(centroidPoint.y - sameRingY) < 1e-9, `y ${centroidPoint.y} vs ${sameRingY}`)
  // And the original two-run ring is the same picture up to the added point.
  assert.ok(Number.isFinite(ringX) && Number.isFinite(ringY))
})

test('tuningTarget: a member is measured against the centre it helps define', () => {
  const t = tuningTarget(profile, [], GROUP, 'B', 1.0)!
  assert.equal(t.inGroup, true)
  assert.equal(t.members, 3)
  // B sits at 0.06 on P1, exactly the group mean — nothing to do there.
  assert.ok(Math.abs(rowFor(t, 'P1').deltaNm) < 1e-12)
  // ...but it is 0.02 above the P2 centre, so a member still gets an instruction.
  assert.ok(Math.abs(rowFor(t, 'P2').deltaNm - -0.02) < 1e-12)
  assert.equal(rowFor(t, 'P2').withinTolerance, true)
})

test('tuningTarget: the tolerance verdict is per parameter, at that parameter\'s own CD', () => {
  // 0.15 nm allowance at index 1.0; D needs 0.24 on P1 and 0.06 on P2.
  const t = tuningTarget(profile, [], GROUP, 'D', 1.0)!
  assert.equal(rowFor(t, 'P1').withinTolerance, false)
  assert.equal(rowFor(t, 'P2').withinTolerance, true)
  assert.ok(Math.abs(rowFor(t, 'P1').toleranceNm - 0.15) < 1e-12)

  // A wide column has a proportionally wider allowance, so the SAME delta can
  // pass on one parameter and fail on another.
  const mixed: ParameterProfile = {
    parameters: [axis('NARROW'), { name: 'WIDE', median_cd_nm: 60, tools: 4 }],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0, 0], [0.2, 0.2]]
  }
  const m = tuningTarget(mixed, [], ['A', 'B'], 'D', 1.0)!
  assert.equal(rowFor(m, 'NARROW').withinTolerance, false) // 0.2 > 0.15
  assert.equal(rowFor(m, 'WIDE').withinTolerance, true) // 0.2 < 0.60
})

test('tuningTarget: rows are worst-first by CD-relative index, not by raw nm', () => {
  const mixed: ParameterProfile = {
    parameters: [{ name: 'WIDE', median_cd_nm: 60, tools: 3 }, axis('NARROW')],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0, 0], [0.30, 0.20]]
  }
  const t = tuningTarget(mixed, [], ['A', 'B'], 'D', 1.0)!
  // WIDE needs the larger nm move (0.30 vs 0.20) but NARROW is further past
  // its own limit (1.33x vs 0.50x), so NARROW leads.
  assert.equal(t.rows[0]!.name, 'NARROW')
  assert.equal(t.worst!.name, 'NARROW')
})

test('tuningTarget: selecting parameters narrows the table to the map\'s columns', () => {
  const t = tuningTarget(profile, ['P2'], GROUP, 'D', 1.0)!
  assert.deepEqual(t.parameters, ['P2'])
  assert.equal(t.rows.length, 1)
  assert.equal(t.rows[0]!.name, 'P2')
  // And the centroid over one column is that column's mean, unchanged by the
  // dropped one.
  assert.ok(Math.abs(t.rows[0]!.centroidNm - 0.01) < 1e-12)
})

test('tuningTarget: a tool that did not measure a used column has no target', () => {
  const holey: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'B', 'D'],
    values: [[0, 0], [0.06, 0.03], [0.30, null]]
  }
  const t = tuningTarget(holey, [], ['A', 'B'], 'D', 1.0)!
  assert.equal(t.placed, false)
  assert.deepEqual(t.rows, [])
  assert.equal(t.worst, null)
  // The map drops it for the same reason, so the two agree about who is absent.
  assert.ok(parameterPca(holey, [], ['A', 'B', 'D'])!.detached.includes('D'))
})

test('tuningTarget: an unplaceable member is left out of the mean, not counted at consensus', () => {
  const holey: ParameterProfile = {
    parameters: [axis('P1'), axis('P2')],
    tools: ['A', 'B', 'C', 'D'],
    values: [[0, 0], [0.06, 0.03], [0.12, null], [0.30, -0.05]]
  }
  const t = tuningTarget(holey, [], GROUP, 'D', 1.0)!
  assert.equal(t.members, 2, 'C measured no P2, so the map cannot place it either')
  // Mean of A and B only: 0.03, not the 0.06 that including C would give.
  assert.ok(Math.abs(rowFor(t, 'P1').centroidNm - 0.03) < 1e-12)
})

test('tuningTarget: nothing to aim at returns null rather than an empty table', () => {
  assert.equal(tuningTarget(profile, [], GROUP, null, 1.0), null, 'no tool picked')
  assert.equal(tuningTarget(profile, [], [], 'D', 1.0), null, 'no group')
  const empty: ParameterProfile = { parameters: [], tools: [], values: [] }
  assert.equal(tuningTarget(empty, [], GROUP, 'D', 1.0), null, 'no usable column')
  // A column only one tool measured is not usable, and is not a table either.
  const thin: ParameterProfile = {
    parameters: [{ name: 'P1', median_cd_nm: CD, tools: 1 }],
    tools: ['A', 'D'],
    values: [[0], [0.3]]
  }
  assert.equal(tuningTarget(thin, [], ['A'], 'D', 1.0), null, 'single-tool column')
})
