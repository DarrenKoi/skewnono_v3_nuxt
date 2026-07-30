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

// X = CD_TOP, Y = CD_BOT, four shared chips with a monotone relation.
const twoParamRows = (): MsrFileRow[] => [
  row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
  row({ sequence: 3, chip_number: '1,0', parameter: 'CD_TOP', cd_value: 110 }),
  row({ sequence: 5, chip_number: '2,0', parameter: 'CD_TOP', cd_value: 120 }),
  row({ sequence: 7, chip_number: '3,0', parameter: 'CD_TOP', cd_value: 130 }),
  row({ sequence: 2, chip_number: '0,0', parameter: 'CD_BOT', cd_value: 200 }),
  row({ sequence: 4, chip_number: '1,0', parameter: 'CD_BOT', cd_value: 205 }),
  row({ sequence: 6, chip_number: '2,0', parameter: 'CD_BOT', cd_value: 210 }),
  row({ sequence: 8, chip_number: '3,0', parameter: 'CD_BOT', cd_value: 215 })
]

// ---------------------------------------------------------------------------
// CD ↔ CD exact join
// ---------------------------------------------------------------------------

test('CD↔CD pairs same-chip values even when every sequence differs', () => {
  const res = buildCdCdRelationship(twoParamRows(), 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 4)
  assert.equal(res.missingN, 0)
  assert.equal(res.readiness, 'ready')
  assert.ok(res.pearson != null && res.pearson > 0.99)
  assert.ok(res.spearman != null && res.spearman > 0.99)
  assert.deepEqual(res.points.map(p => p.chip), ['0,0', '1,0', '2,0', '3,0'])
  assert.deepEqual(res.points[0], {
    key: '0,0',
    chip: '0,0',
    sequence: 1,
    x: 100,
    y: 200
  })
})

test('different chips produce zero pairs and an unavailable result', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1,0', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 0)
  assert.equal(res.missingN, 2)
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

test('a chip present on only one axis is dropped and counted once', () => {
  const rows: MsrFileRow[] = [
    row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 3, chip_number: '1,0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 2, chip_number: '0,0', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.equal(res.missingN, 1)
  assert.equal(res.points[0]?.chip, '0,0')
})

test('one row per axis pairs by chip and ignores coordinate differences', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.equal(res.points[0]?.key, '0,0')
})

test('repeated rows with equal coordinate sets pair per coordinate and average repeats', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 104 }),
    row({ sequence: 13, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.deepEqual(res.points.map(p => [p.key, p.x, p.y]), [
    ['0,0#10,10', 102, 200],
    ['0,0#20,20', 110, 220]
  ])
})

test('missing coordinates fall back to one per-parameter chip mean', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.deepEqual(res.points[0], {
    key: '0,0',
    chip: '0,0',
    sequence: 11,
    x: 105,
    y: 210
  })
})

test('different coordinate sets fall back to one per-parameter chip mean', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '30,30', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.deepEqual([res.points[0]?.x, res.points[0]?.y], [105, 210])
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
