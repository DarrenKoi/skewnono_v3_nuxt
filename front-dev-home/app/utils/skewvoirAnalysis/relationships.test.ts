// front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts
// Pure-logic tests for the single-MSR exact-pair relationship join.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/relationships.test.ts
//
// THE JOIN IS THE CRUX: parameters are paired by a SHARED SITE/SEQUENCE KEY,
// never by array index. A row missing in one parameter is dropped from pairing
// and counted as `missing`, never smeared against a differently-keyed row.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCdCdRelationship, buildCdFdcRelationship } from './relationships.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// X = CD_TOP, Y = CD_BOT, four shared sites with a monotone relation.
const twoParamRows = (): MsrFileRow[] => [
  row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 }),
  row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: 110 }),
  row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_TOP', cd_value: 120 }),
  row({ sequence: 4, chip_number: '3, 0', parameter: 'CD_TOP', cd_value: 130 }),
  row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_BOT', cd_value: 200 }),
  row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_BOT', cd_value: 205 }),
  row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_BOT', cd_value: 210 }),
  row({ sequence: 4, chip_number: '3, 0', parameter: 'CD_BOT', cd_value: 215 })
]

// ---------------------------------------------------------------------------
// CD ↔ CD exact join
// ---------------------------------------------------------------------------

test('CD↔CD pairs by shared site key and reports Pearson/Spearman + N', () => {
  const res = buildCdCdRelationship(twoParamRows(), 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 4)
  assert.equal(res.missingN, 0)
  assert.equal(res.readiness, 'ready')
  assert.ok(res.pearson != null && res.pearson > 0.99)
  assert.ok(res.spearman != null && res.spearman > 0.99)
  // Each paired point is keyed correctly: X=CD_TOP value, Y=CD_BOT value.
  const p1 = res.points.find(p => p.sequence === 1)!
  assert.equal(p1.x, 100)
  assert.equal(p1.y, 200)
  assert.equal(p1.chip, '0, 0')
})

test('zero pairs ⇒ 평가 불가 (unavailable), NOT r=0', () => {
  // Two params that share no site key at all (disjoint sequences).
  const rows: MsrFileRow[] = [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 0)
  assert.equal(res.readiness, 'unavailable')
  assert.equal(res.pearson, null)
  assert.equal(res.spearman, null)
})

test('constant axis ⇒ 평가 불가 (unavailable), NOT r=0', () => {
  // Y is constant across all shared sites: zero variance ⇒ correlation undefined.
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_TOP', cd_value: 120 }),
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_BOT', cd_value: 205 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_BOT', cd_value: 205 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_BOT', cd_value: 205 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 3)
  assert.equal(res.readiness, 'unavailable')
  assert.equal(res.pearson, null)
})

test('a missing row in X is DROPPED and counted, never index-paired against Y', () => {
  // Y has sequences 1..4; X is MISSING sequence 1 (a gap at the FIRST key).
  // Index pairing would shift every X down one row and pair X(seq2) with
  // Y(seq1) — the key join must instead pair by sequence and drop seq 1.
  const rows: MsrFileRow[] = [
    // X = CD_TOP, gap at seq 1
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_TOP', cd_value: 120 }),
    row({ sequence: 4, chip_number: '3, 0', parameter: 'CD_TOP', cd_value: 130 }),
    // Y = CD_BOT, full 1..4
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_BOT', cd_value: 205 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_BOT', cd_value: 210 }),
    row({ sequence: 4, chip_number: '3, 0', parameter: 'CD_BOT', cd_value: 215 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  // seq 1 is present only in Y → dropped, counted as missing.
  assert.equal(res.pairN, 3)
  assert.equal(res.missingN, 1)
  assert.deepEqual(res.points.map(p => p.sequence).sort(), [2, 3, 4])
  // The surviving pairs are correctly keyed, NOT index-shifted.
  const p2 = res.points.find(p => p.sequence === 2)!
  assert.equal(p2.x, 110) // CD_TOP@seq2
  assert.equal(p2.y, 205) // CD_BOT@seq2  (index pairing would give 200)
  const p4 = res.points.find(p => p.sequence === 4)!
  assert.equal(p4.x, 130)
  assert.equal(p4.y, 215)
})

test('unmeasured (mp_number < 0 / null cd) rows are excluded via isMeasuredRow', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: null, mp_number: -1 }),
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_BOT', cd_value: 205 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  // seq 2 X is a failure row → not a measured X key; seq 2 Y is measured-only.
  assert.equal(res.pairN, 1)
  assert.equal(res.missingN, 1)
})

// ---------------------------------------------------------------------------
// CD ↔ dynamic FDC join (same MSR + same sequence)
// ---------------------------------------------------------------------------

test('CD↔FDC joins on same MSR + sequence and flags the demo coupling', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_TOP', cd_value: 120 })
  ]
  const dynamicFdc: Record<string, Record<string, number>> = {
    1: { focus: 2.0 },
    2: { focus: 2.5 },
    3: { focus: 3.0 }
  }
  const res = buildCdFdcRelationship(rows, 'CD_TOP', 'focus', dynamicFdc)
  assert.equal(res.pairN, 3)
  assert.equal(res.readiness, 'ready')
  assert.equal(res.sameMsrSequenceJoin, true)
  assert.equal(res.demoCoupled, true)
  assert.ok(res.pearson != null && res.pearson > 0.99)
  const p1 = res.points.find(p => p.sequence === 1)!
  assert.equal(p1.x, 100)
  assert.equal(p1.y, 2.0)
})

test('CD↔FDC drops sequences absent from dynamic_fdc and counts them missing', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1, 0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 3, chip_number: '2, 0', parameter: 'CD_TOP', cd_value: 120 })
  ]
  // dynamic_fdc missing seq 2 for this param.
  const dynamicFdc: Record<string, Record<string, number>> = {
    1: { focus: 2.0 },
    3: { focus: 3.0 }
  }
  const res = buildCdFdcRelationship(rows, 'CD_TOP', 'focus', dynamicFdc)
  assert.equal(res.pairN, 2)
  assert.equal(res.missingN, 1)
  assert.deepEqual(res.points.map(p => p.sequence).sort(), [1, 3])
})

test('CD↔FDC with zero overlap ⇒ 평가 불가 (unavailable)', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0, 0', parameter: 'CD_TOP', cd_value: 100 })
  ]
  const res = buildCdFdcRelationship(rows, 'CD_TOP', 'focus', {})
  assert.equal(res.pairN, 0)
  assert.equal(res.readiness, 'unavailable')
  assert.equal(res.pearson, null)
})
