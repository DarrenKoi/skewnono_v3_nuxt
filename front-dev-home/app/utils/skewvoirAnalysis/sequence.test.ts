// front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts
// Pure-logic tests for the single-MSR measurement-order (sequence) workbench.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/sequence.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSequence } from './sequence.ts'
import type { MsrFileRow, FdcParamSummary } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: 'img_0001.svg', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

const fdcParam = (over: Partial<FdcParamSummary>): FdcParamSummary => ({
  name: 'StigmaX', category: 'astigmatism', category_label: '비점수차', unit: 'a.u.',
  nominal: 10, mean: 13, std: 2.2, min: 10, max: 16, drift_sigma: 1.3, status: 'ok',
  ...over
})

// CD rises +2 nm/sequence: seq 1/2/4 measured 100/102/106; seq 3 is a FAILURE
// (cd null, mp -1). Dynamic FDC StigmaX rises +2/sequence: 10/12/14/16.
const source = () => ({
  rows: [
    row({ sequence: 1, chip_number: '0, 0', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1, 0', cd_value: 102 }),
    row({ sequence: 3, chip_number: '2, 0', cd_value: null, mp_number: -1, no_of_mp_image: 0, mp_image_name_01: '', addressing1_score: null, addressing2_score: null }),
    row({ sequence: 4, chip_number: '3, 0', cd_value: 106 })
  ],
  dynamic_fdc: {
    1: { StigmaX: 10 },
    2: { StigmaX: 12 },
    3: { StigmaX: 14 },
    4: { StigmaX: 16 }
  },
  fdc_params: [fdcParam({})]
})

const noFdcSource = () => ({
  rows: [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 102 })
  ],
  dynamic_fdc: {},
  fdc_params: []
})

// ---------------------------------------------------------------------------
// CD sequence series
// ---------------------------------------------------------------------------

test('CD series carries one point per sequence, in measurement order, with nulls preserved', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')
  assert.deepEqual(m.cd.points.map(p => p.sequence), [1, 2, 3, 4])
  assert.deepEqual(m.cd.points.map(p => p.value), [100, 102, null, 106])
  assert.deepEqual(m.cd.points.map(p => p.measured), [true, true, false, true])
})

test('CD stats: start/end/range/slope/missing over the SEQUENCE (per sequence, not per second)', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')
  assert.equal(m.cd.stats.start, 100) // first measured
  assert.equal(m.cd.stats.end, 106) // last measured
  assert.equal(m.cd.stats.range, 6) // max(106) - min(100)
  assert.ok(Math.abs(m.cd.stats.slope - 2) < 1e-9) // OLS of (1,100)(2,102)(4,106)
  assert.equal(m.cd.stats.missing, 1) // the failed seq-3 point
  assert.equal(m.cd.stats.n, 3)
  assert.equal(m.cd.stats.unit, 'nm')
  assert.equal(m.cd.stats.slopeUnit, 'nm per sequence')
})

// ---------------------------------------------------------------------------
// Dynamic FDC series (separate panes, aligned on the shared sequence axis)
// ---------------------------------------------------------------------------

test('dynamic FDC series align on the same sequence axis as CD', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')
  assert.deepEqual(m.sequences, [1, 2, 3, 4])
  assert.equal(m.fdc.length, 1)
  const s = m.fdc[0]!
  assert.equal(s.param, 'StigmaX')
  assert.equal(s.unit, 'a.u.')
  assert.deepEqual(s.points.map(p => p.sequence), [1, 2, 3, 4])
  assert.deepEqual(s.points.map(p => p.value), [10, 12, 14, 16])
  assert.ok(Math.abs(s.stats.slope - 2) < 1e-9)
  assert.equal(s.stats.slopeUnit, 'a.u. per sequence')
})

test('shared-cursor model maps every sequence to its site (chip) for focusedSite linkage', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')
  assert.equal(m.siteBySequence[1], '0, 0')
  assert.equal(m.siteBySequence[3], '2, 0')
  assert.equal(m.siteBySequence[4], '3, 0')
})

// ---------------------------------------------------------------------------
// Event lane
// ---------------------------------------------------------------------------

test('event lane places failure / image / alignment evidence along the sequence axis', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')
  const bySeq = new Map(m.events.map(e => [e.sequence, e]))
  assert.equal(bySeq.get(1)!.image, true)
  assert.equal(bySeq.get(1)!.alignment, true)
  assert.equal(bySeq.get(1)!.failure, false)
  assert.equal(bySeq.get(3)!.failure, true)
  assert.equal(bySeq.get(3)!.image, false)
  assert.equal(bySeq.get(3)!.alignment, false)
})

// ---------------------------------------------------------------------------
// No-FDC MSR
// ---------------------------------------------------------------------------

test('an MSR with no dynamic FDC yields the CD pane only, with a reason', () => {
  const m = analyzeSequence(noFdcSource(), 'CD_TOP', 'nm')
  assert.equal(m.hasFdc, false)
  assert.equal(m.fdc.length, 0)
  assert.ok(m.fdcReason && m.fdcReason.length > 0)
  assert.equal(m.cd.points.length, 2)
})

// ---------------------------------------------------------------------------
// CRITICAL: no time-based slope / time-lag anywhere (mock has no per-sequence
// timestamp, so any per-second rate or lag would be fabricated).
// ---------------------------------------------------------------------------

test('the model exposes NO time-based slope or time-lag output — only per-sequence', () => {
  const m = analyzeSequence(source(), 'CD_TOP', 'nm')

  // Every slope unit is per-sequence, never per-second.
  const slopeUnits = [m.cd.stats.slopeUnit, ...m.fdc.map(f => f.stats.slopeUnit)]
  for (const u of slopeUnits) {
    assert.ok(u.endsWith('per sequence'), `slopeUnit must be per-sequence, got "${u}"`)
    assert.doesNotMatch(u, /second/i)
  }

  // No key anywhere in the model hints at time / seconds / lag.
  const keys: string[] = []
  const walk = (v: unknown) => {
    if (Array.isArray(v)) return v.forEach(walk)
    if (v && typeof v === 'object') {
      for (const [k, val] of Object.entries(v)) {
        keys.push(k)
        walk(val)
      }
    }
  }
  walk(m)
  for (const k of keys) {
    assert.doesNotMatch(k, /(?:per)?second|timelag|time_lag|timestamp|elapsed/i, `unexpected time-based key "${k}"`)
  }
})
