// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseWaferGeometry, stagePosMm, dieCenterMm, siteRadiusMm, mmToDieIndex } from './waferGeometry.ts'
import type { ExeDetailInfo } from '~/composables/useMsrFileApi'

const info = (over: Partial<ExeDetailInfo> = {}): ExeDetailInfo => ({
  class_name: 'CD', recipe_name: '', idp_name: '', lot_id: '', process: '',
  wafer_id: '', idw_name: '', chip_array: '44,52', chip_pitch: '6818182,5769231',
  wafer_size: '300', map_offset: '0,0', map_origin: '150000000,150000000',
  ...over
})

test('parseWaferGeometry reads size, radius, centre and pitch (nm → mm)', () => {
  const g = parseWaferGeometry(info())
  assert.equal(g.sizeMm, 300)
  assert.equal(g.radiusMm, 150)
  assert.equal(g.centerNm, 150_000_000)
  assert.ok(Math.abs(g.pitchXmm - 6.818182) < 1e-6)
  assert.ok(Math.abs(g.pitchYmm - 5.769231) < 1e-6)
})

test('parseWaferGeometry falls back to a 300 mm wafer when info is missing', () => {
  const g = parseWaferGeometry(null)
  assert.equal(g.sizeMm, 300)
  assert.equal(g.radiusMm, 150)
  assert.equal(g.pitchXmm, 0)
})

test('stagePosMm converts a corner-origin nm stage to mm from centre', () => {
  const g = parseWaferGeometry(info())
  // 10 mm right and 20 mm above centre
  const p = stagePosMm('160000000,170000000', g)
  assert.deepEqual(p, [10, 20])
})

test('stagePosMm rejects malformed coordinates', () => {
  const g = parseWaferGeometry(info())
  assert.equal(stagePosMm('nope', g), null)
  assert.equal(stagePosMm('1,2,3', g), null)
})

test('dieCenterMm places die (col,row) on the pitch grid', () => {
  const g = parseWaferGeometry(info())
  const [x, y] = dieCenterMm(2, -3, g)
  assert.ok(Math.abs(x - 2 * g.pitchXmm) < 1e-9)
  assert.ok(Math.abs(y - -3 * g.pitchYmm) < 1e-9)
})

test('siteRadiusMm is the distance from wafer centre', () => {
  const g = parseWaferGeometry(info())
  // (3,4) mm from centre → radius 5 mm
  const r = siteRadiusMm('153000000,154000000', g)
  assert.ok(r != null && Math.abs(r - 5) < 1e-9)
})

test('mmToDieIndex rounds mm to the nearest die column/row', () => {
  assert.equal(mmToDieIndex(0, 6.818182), 0)
  assert.equal(mmToDieIndex(6.9, 6.818182), 1)
  assert.equal(mmToDieIndex(-13.6, 6.818182), -2)
})

test('mmToDieIndex returns null when pitch is unknown', () => {
  assert.equal(mmToDieIndex(50, 0), null)
})
