// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isValidRow, validRows, paramValues } from './msrRows.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 10,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

test('a null cd_value is invalid', () => {
  assert.equal(isValidRow(row({ cd_value: null, mp_number: -1 })), false)
})

test('mp_number < 0 is invalid even if a cd_value somehow survives', () => {
  // Defence in depth: the office backend may not honour the null contract.
  assert.equal(isValidRow(row({ mp_number: -1, cd_value: 42 })), false)
})

// Every case above pairs mp_number: -1 with cd_value: null, so deleting the
// `cd_value != null` clause of isValidRow would leave them all green. Pin it
// in isolation: mp_number is a valid non-sentinel, but cd_value is still null.
test('mp_number >= 0 with a null cd_value is invalid — the null is the backend contract', () => {
  assert.equal(isValidRow(row({ mp_number: 0, cd_value: null })), false)
})

test('non-finite cd_value is invalid', () => {
  assert.equal(isValidRow(row({ cd_value: Number.NaN })), false)
  assert.equal(isValidRow(row({ cd_value: Number.POSITIVE_INFINITY })), false)
})

test('mp_number 0 is valid — only negatives are sentinels', () => {
  assert.equal(isValidRow(row({ mp_number: 0 })), true)
})

test('validRows drops invalid rows and preserves order', () => {
  const rows = [
    row({ sequence: 1 }),
    row({ sequence: 2, mp_number: -1, cd_value: null }),
    row({ sequence: 3 })
  ]
  assert.deepEqual(validRows(rows).map(r => r.sequence), [1, 3])
})

test('paramValues filters by parameter AND validity', () => {
  const rows = [
    row({ parameter: 'CD_TOP', cd_value: 10 }),
    row({ parameter: 'CD_BOTTOM', cd_value: 20 }),
    row({ parameter: 'CD_TOP', cd_value: null, mp_number: -1 }),
    row({ parameter: 'CD_TOP', cd_value: 12 })
  ]
  assert.deepEqual(paramValues(rows, 'CD_TOP'), [10, 12])
})

test('empty input yields empty output', () => {
  assert.deepEqual(validRows([]), [])
  assert.deepEqual(paramValues([], 'CD_TOP'), [])
})
