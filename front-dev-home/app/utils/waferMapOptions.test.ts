// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { defaultWaferMapOptions, detailWaferMapOptions, resolveColorRange } from './waferMapOptions.ts'

test('defaultWaferMapOptions: notch on, everything else off, auto color', () => {
  const o = defaultWaferMapOptions()
  assert.equal(o.crosshair, false)
  assert.equal(o.grid, false)
  assert.equal(o.mpLabels, false)
  assert.equal(o.notch, true)
  assert.equal(o.colorMode, 'auto')
  assert.equal(o.colorMin, null)
  assert.equal(o.colorMax, null)
})

test('detailWaferMapOptions: like default but grid on', () => {
  const o = detailWaferMapOptions()
  assert.equal(o.grid, true)
  assert.equal(o.notch, true)
})

test('resolveColorRange: auto mode returns the auto range', () => {
  assert.deepEqual(resolveColorRange('auto', 1, 9, { min: 3, max: 7 }), { min: 3, max: 7 })
})

test('resolveColorRange: valid manual overrides auto', () => {
  assert.deepEqual(resolveColorRange('manual', 1, 9, { min: 3, max: 7 }), { min: 1, max: 9 })
})

test('resolveColorRange: manual falls back to auto when incomplete or inverted', () => {
  assert.deepEqual(resolveColorRange('manual', null, 9, { min: 3, max: 7 }), { min: 3, max: 7 })
  assert.deepEqual(resolveColorRange('manual', 9, 1, { min: 3, max: 7 }), { min: 3, max: 7 })
})

test('resolveColorRange: manual rejects non-finite (blank input → NaN)', () => {
  assert.deepEqual(resolveColorRange('manual', Number.NaN, 9, { min: 3, max: 7 }), { min: 3, max: 7 })
})
