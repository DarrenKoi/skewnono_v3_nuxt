// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { WaferGeometry } from './waferGeometry.ts'
import { buildWaferPoints } from './waferPoints.ts'

// 1 mm pitch, centre at 150 mm → stage "150000000,150000000" is wafer centre (0,0).
const geo: WaferGeometry = { sizeMm: 300, radiusMm: 150, centerNm: 150_000_000, pitchXmm: 1, pitchYmm: 1 }

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M', sequence: 1, chip_number: '0,0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '', mp_number: 0, parameter: 'CD_X', cd_value: 10, no_of_mp_image: 0, mp_image_name_01: '',
  meas_condition_mag: 0, meas_condition_vac: 0, meas_condition_pixel: '', addressing1_score: null,
  addressing2_score: null, measurement_score: null, meas_method: '', object_type: '', meas_kind: null,
  ...over
})

const rows: MsrFileRow[] = [
  row({ sequence: 1, chip_number: '2,3', stage_coordinate: '152000000,153000000', mp_number: 5, cd_value: 40 }),
  row({ sequence: 2, chip_number: '2,3', stage_coordinate: '152500000,153500000', mp_number: 6, cd_value: 50 }),
  row({ sequence: 3, chip_number: '0,0', stage_coordinate: '150000000,150000000', mp_number: 0, cd_value: 30 }),
  row({ sequence: 4, chip_number: '1,1', stage_coordinate: '151000000,151000000', mp_number: -1, cd_value: null })
]

test('fieldPoints: one point per measured row, at its own stage position, n=1', () => {
  const { fieldPoints } = buildWaferPoints(rows, geo)
  assert.equal(fieldPoints.length, 3)
  const a = fieldPoints.find(p => p.seq === 1)!
  assert.deepEqual([a.x, a.y], [2, 3])
  assert.equal(a.mp, 5)
  assert.equal(a.value, 40)
  assert.equal(a.n, 1)
  assert.deepEqual(a.seqs, [1])
})

test('diePoints: aggregates rows on the same die (mean value, both seqs, grid centre)', () => {
  const { diePoints } = buildWaferPoints(rows, geo)
  assert.equal(diePoints.length, 2)
  const d = diePoints.find(p => p.field === '2,3')!
  assert.equal(d.n, 2)
  assert.equal(d.value, 45) // mean(40, 50)
  assert.deepEqual([d.x, d.y], [2, 3]) // dieCenterMm(2,3) with 1 mm pitch
  assert.deepEqual(d.seqs.sort(), [1, 2])
})

test('failurePoints: unmeasured rows at their physical position', () => {
  const { failurePoints } = buildWaferPoints(rows, geo)
  assert.equal(failurePoints.length, 1)
  assert.equal(failurePoints[0]!.seq, 4)
  assert.deepEqual([failurePoints[0]!.x, failurePoints[0]!.y], [1, 1])
})
