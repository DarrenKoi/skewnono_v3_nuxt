// front-dev-home/app/utils/anomaly/site.test.ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { siteVerdicts } from './site.ts'
import { DEFAULT_METHOD_CONFIG } from './types.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

test('a site far from its peers is abnormal; the rest are normal', () => {
  // Peers sit at 100; one site at 130 is +30% off the LOO mean (abnormalPct = 20).
  const rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 100 }),
    row({ sequence: 4, cd_value: 130 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 4)
  assert.equal(out[3]!.verdict.severity, 'abnormal')
  assert.equal(out[0]!.verdict.severity, 'normal')
})

test('unmeasured rows are excluded — they cannot be judged nor judge others', () => {
  const rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 100 }),
    row({ sequence: 4, cd_value: null, mp_number: -1 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 3)
  assert.ok(out.every(o => o.verdict.severity === 'normal'))
})

test('other parameters are ignored', () => {
  const rows = [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 3, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 4, parameter: 'CD_BOTTOM', cd_value: 5 })
  ]
  assert.equal(siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG).length, 3)
})

test('too few sites yields insufficient, not normal', () => {
  const rows = [row({ sequence: 1, cd_value: 100 }), row({ sequence: 2, cd_value: 100 })]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 2)
  assert.ok(out.every(o => o.verdict.status === 'insufficient'))
})

test('the verdict is paired back to its originating row', () => {
  const rows = [
    row({ sequence: 1, chip_number: '1, 1', cd_value: 100 }),
    row({ sequence: 2, chip_number: '2, 2', cd_value: 100 }),
    row({ sequence: 3, chip_number: '3, 3', cd_value: 100 }),
    row({ sequence: 4, chip_number: '9, 9', cd_value: 130 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.find(o => o.verdict.severity === 'abnormal')!.row.chip_number, '9, 9')
})

test('empty input yields empty output', () => {
  assert.deepEqual(siteVerdicts([], 'CD_TOP', DEFAULT_METHOD_CONFIG), [])
})
