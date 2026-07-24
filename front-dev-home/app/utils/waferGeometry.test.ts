// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseWaferGeometry, stagePosMm, dieCenterMm, siteRadiusMm, mmToDieIndex, snapToDieCell } from './waferGeometry.ts'
import type { ExeDetailInfo } from '~/composables/useMsrFileApi'

// Office-confirmed formats (2026-07-24): all strings, wafer_size in nm,
// map_origin = array index of the origin die.
const info = (over: Partial<ExeDetailInfo> = {}): ExeDetailInfo => ({
  class_name: 'CD', recipe_name: '', idp_name: '', lot_id: '', process: '',
  wafer_id: '', idw_name: '', chip_array: '44,52', chip_pitch: '6818182,5769231',
  wafer_size: '300000000', map_offset: '0,0', map_origin: '22,26',
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

test('parseWaferGeometry accepts a legacy mm wafer_size', () => {
  const g = parseWaferGeometry(info({ wafer_size: '300' }))
  assert.equal(g.sizeMm, 300)
  assert.equal(g.centerNm, 150_000_000)
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

test('parseWaferGeometry reads map_offset (nm → mm) and map_origin', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000', map_origin: '12,15' }))
  assert.equal(g.offsetXmm, 0)
  assert.ok(Math.abs(g.offsetYmm - 4.61) < 1e-9)
  assert.equal(g.originCol, 12)
  assert.equal(g.originRow, 15)
})

test('parseWaferGeometry defaults map_offset/map_origin to 0 when blank or absent', () => {
  const g = parseWaferGeometry(info({ map_offset: '', map_origin: '' }))
  assert.equal(g.offsetXmm, 0)
  assert.equal(g.offsetYmm, 0)
  assert.equal(g.originCol, 0)
  assert.equal(g.originRow, 0)
  const none = parseWaferGeometry(null)
  assert.equal(none.offsetXmm, 0)
  assert.equal(none.originCol, 0)
})

// Regression pin: map_offset shifts the DIE GRID, not the wafer. A point's
// position from the wafer centre must not move, or radius/sector would drift.
test('stagePosMm is measured from the wafer centre, unaffected by map_offset', () => {
  const g = parseWaferGeometry(info({ map_offset: '3000000,4610000' }))
  assert.deepEqual(stagePosMm('160000000,170000000', g), [10, 20])
})

test('dieCenterMm shifts die centres by the die-grid offset', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000' }))
  const [x, y] = dieCenterMm(2, -3, g)
  assert.ok(Math.abs(x - 2 * g.pitchXmm) < 1e-9) // offsetXmm is 0 here
  assert.ok(Math.abs(y - (4.61 + -3 * g.pitchYmm)) < 1e-9)
})

test('dieCenterMm applies the offset per axis (X and Y are not transposed)', () => {
  const g = parseWaferGeometry(info({ map_offset: '3000000,4610000' }))
  const [x, y] = dieCenterMm(2, -3, g)
  // offsetXmm=3, offsetYmm=4.61; dies at (2,-3) should have distinct coords
  assert.ok(Math.abs(x - (3 + 2 * g.pitchXmm)) < 1e-9)
  assert.ok(Math.abs(y - (4.61 + -3 * g.pitchYmm)) < 1e-9)
})

test('mmToDieIndex accounts for the die-grid offset', () => {
  const pitch = 6.818182
  assert.equal(mmToDieIndex(4.61, pitch, 4.61), 0)
  assert.equal(mmToDieIndex(4.61 + pitch, pitch, 4.61), 1)
  assert.equal(mmToDieIndex(4.61 - 2 * pitch, pitch, 4.61), -2)
})

test('mmToDieIndex offset defaults to zero for existing callers', () => {
  assert.equal(mmToDieIndex(6.9, 6.818182), 1)
})

// A stage_coordinate string (corner-origin nm) for a point at (xMm, yMm) from
// the wafer centre — the inverse of stagePosMm, used to build round-trip cases.
const stageAt = (xMm: number, yMm: number, g: ReturnType<typeof parseWaferGeometry>): string =>
  `${xMm * 1_000_000 + g.centerNm},${yMm * 1_000_000 + g.centerNm}`

test('snapToDieCell round-trips a die centre plus sub-half-pitch jitter', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000' }))
  const [cx, cy] = dieCenterMm(3, -4, g)
  // Measured points sit within their die: the mock jitters up to 0.3·pitch.
  assert.equal(snapToDieCell(stageAt(cx + 0.3 * g.pitchXmm, cy - 0.3 * g.pitchYmm, g), g), '3,-4')
  assert.equal(snapToDieCell(stageAt(cx, cy, g), g), '3,-4')
})

test('snapToDieCell ignoring the offset would land on the wrong die', () => {
  // Guard the offset actually participates: a die centre one full pitch of
  // offset away must not snap to the unshifted cell.
  const g = parseWaferGeometry(info({ map_offset: '0,5769231' })) // = 1·pitchY
  const [cx, cy] = dieCenterMm(0, 0, g)
  assert.equal(snapToDieCell(stageAt(cx, cy, g), g), '0,0')
})

test('snapToDieCell applies the offset per axis (X and Y are not transposed or dropped)', () => {
  // Both axes non-zero and distinct, so a sign/axis error on either one is
  // caught here even if a same-named test elsewhere happens to zero one out.
  const g = parseWaferGeometry(info({ map_offset: '3000000,4610000' }))
  const [cx, cy] = dieCenterMm(2, -3, g)
  assert.equal(snapToDieCell(stageAt(cx, cy, g), g), '2,-3')
})

test('snapToDieCell returns null without a pitch or on a bad coordinate', () => {
  assert.equal(snapToDieCell('160000000,170000000', parseWaferGeometry(info({ chip_pitch: '' }))), null)
  assert.equal(snapToDieCell('nope', parseWaferGeometry(info())), null)
  assert.equal(snapToDieCell('1,2,3', parseWaferGeometry(info())), null)
})
