// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  profileMetricKeys, scalarMetricKeys, radialRange, degreeLabels, prettyLabel,
  type BeamMetricOption
} from './beamMetrics.ts'

const arr16 = (base: number) => Array.from({ length: 16 }, (_, i) => base + i * 0.01)

const doc = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  'degree': [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5],
  'Reso EB': arr16(8.0),
  'Reso Detector': arr16(0.005),
  'Reso EB Focus Range': ['8.0000'],
  'Ellipicity': 1.023,
  'Major Axis': 8.12,
  'Ave. Noise': '6.277',          // numeric string scalar
  'type': 'total',
  'beam_condition': 'HR0800_IP0080',
  'eqp_id': 'ECXDX1234',
  ...overrides
})

test('profileMetricKeys: only length-16 numeric arrays, degree + Focus Range excluded', () => {
  const keys = profileMetricKeys([doc()]).map(o => o.key).sort()
  assert.deepEqual(keys, ['Reso Detector', 'Reso EB'])
})

test('profileMetricKeys: rejects a short array', () => {
  const keys = profileMetricKeys([doc({ 'Reso EB': [1, 2, 3] })]).map(o => o.key)
  assert.ok(!keys.includes('Reso EB'))
})

test('scalarMetricKeys: numbers and numeric strings, no arrays/metadata', () => {
  const keys = scalarMetricKeys([doc()]).map(o => o.key).sort()
  assert.deepEqual(keys, ['Ave. Noise', 'Ellipicity', 'Major Axis'])
})

test('radialRange: global min/max across docs, padded, never zero span', () => {
  const r = radialRange([doc({ 'Reso EB': arr16(8.0) }), doc({ 'Reso EB': arr16(9.0) })], 'Reso EB')
  // values span 8.00 .. 9.15 → padded outward
  assert.ok(r.min < 8.0)
  assert.ok(r.max > 9.15)
})

test('radialRange: missing key → {0,1}', () => {
  assert.deepEqual(radialRange([doc()], 'Nope'), { min: 0, max: 1 })
})

test('degreeLabels: first doc degree as strings', () => {
  assert.deepEqual(degreeLabels([doc()])[1], '22.5')
})

test('prettyLabel: keeps source spellings verbatim when unknown', () => {
  assert.equal(prettyLabel('Apature angle factor'), 'Apature angle factor')
})
