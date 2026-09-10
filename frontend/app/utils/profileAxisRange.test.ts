// Pure-logic tests for profileAxisRange. Run: node --test app/utils/profileAxisRange.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canonicalMetricKey, defaultRangeFor, isValidRange, resolveAxisRange
} from './profileAxisRange.ts'

const DERIVED = { min: 0, max: 1 }

test('the two tab spellings of a metric collapse to one key', () => {
  // Sharpness dict keys vs. beam_shape array keys — same measurement.
  assert.equal(canonicalMetricKey('Reso EB'), 'reso_eb')
  assert.equal(canonicalMetricKey('reso_eb'), 'reso_eb')
  assert.equal(canonicalMetricKey('RESO_EB'), 'reso_eb')
  assert.equal(canonicalMetricKey('Noise'), 'noise')
  assert.equal(canonicalMetricKey('noise'), 'noise')
})

test('distinct metrics stay distinct after canonicalisation', () => {
  assert.equal(canonicalMetricKey('Ave. Noise'), 'ave_noise')
  assert.notEqual(canonicalMetricKey('Ave. Noise'), canonicalMetricKey('Noise'))
  assert.equal(canonicalMetricKey('Reso Detector'), 'reso_detector')
  assert.equal(canonicalMetricKey('Apature angle factor'), 'apature_angle_factor')
})

test('known metrics get their operating band regardless of spelling', () => {
  assert.deepEqual(defaultRangeFor('reso_eb', DERIVED), { min: 7.5, max: 8.5 })
  assert.deepEqual(defaultRangeFor('Reso EB', DERIVED), { min: 7.5, max: 8.5 })
  assert.deepEqual(defaultRangeFor('noise', DERIVED), { min: 5.7, max: 6.7 })
  assert.deepEqual(defaultRangeFor('Noise', DERIVED), { min: 5.7, max: 6.7 })
})

test('the mock operating bands sit inside their defaults', () => {
  // sharpness reso_eb 8.00±0.30, BSM Reso EB 7.90~8.30; noise 6.10±0.25,
  // BSM Noise 6.00~6.50. A default that clipped live data would be a bug.
  const eb = defaultRangeFor('Reso EB', DERIVED)
  assert.ok(eb.min <= 7.70 && eb.max >= 8.30, 'reso_eb band covers both mocks')
  const noise = defaultRangeFor('Noise', DERIVED)
  assert.ok(noise.min <= 5.85 && noise.max >= 6.50, 'noise band covers both mocks')
})

test('a metric with no operating band falls back to the derived range', () => {
  assert.deepEqual(defaultRangeFor('Focus offset', DERIVED), DERIVED)
  assert.deepEqual(defaultRangeFor('reso_detector', DERIVED), DERIVED)
})

test('range validity rejects inverted, flat, and non-finite pairs', () => {
  assert.equal(isValidRange({ min: 1, max: 2 }), true)
  assert.equal(isValidRange({ min: 2, max: 1 }), false)
  assert.equal(isValidRange({ min: 1, max: 1 }), false)
  assert.equal(isValidRange({ min: NaN, max: 2 }), false)
  assert.equal(isValidRange({ min: 1, max: Infinity }), false)
  assert.equal(isValidRange(null), false)
  assert.equal(isValidRange(undefined), false)
})

test('a valid override beats the operating band', () => {
  assert.deepEqual(
    resolveAxisRange('reso_eb', { min: 7.0, max: 9.0 }, DERIVED),
    { min: 7.0, max: 9.0 }
  )
})

test('an invalid override falls through instead of blanking the chart', () => {
  // Corrupt storage or a half-typed value must not produce an empty axis.
  assert.deepEqual(resolveAxisRange('reso_eb', { min: 9, max: 7 }, DERIVED), { min: 7.5, max: 8.5 })
  assert.deepEqual(resolveAxisRange('reso_eb', { min: NaN, max: 8 }, DERIVED), { min: 7.5, max: 8.5 })
  assert.deepEqual(resolveAxisRange('Focus offset', null, DERIVED), DERIVED)
})
