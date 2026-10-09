// Run: cd frontend && node --test app/utils/scaleLabel.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatScaleLabel, scaleDecimals } from './scaleLabel.ts'

test('formatScaleLabel: decimals follow the magnitude — about three significant digits, never more than three decimals', () => {
  assert.equal(formatScaleLabel(0.3), '0.3')
  assert.equal(formatScaleLabel(-0.3), '-0.3')
  assert.equal(formatScaleLabel(0.0123), '0.012')
  assert.equal(formatScaleLabel(2.4142), '2.41')
  assert.equal(formatScaleLabel(12.345), '12.3')
  assert.equal(formatScaleLabel(45.126), '45.1')
  assert.equal(formatScaleLabel(104.56), '105')
})

test('formatScaleLabel: trailing zeros are dropped', () => {
  assert.equal(formatScaleLabel(45), '45')
  assert.equal(formatScaleLabel(1.5), '1.5')
  assert.equal(formatScaleLabel(0), '0')
})

test('formatScaleLabel: a value that rounds to zero is "0", never "-0"', () => {
  assert.equal(formatScaleLabel(-0.0004), '0')
  assert.equal(formatScaleLabel(-0), '0')
  assert.equal(formatScaleLabel(0.0004), '0')
})

test('formatScaleLabel: no number, no label', () => {
  assert.equal(formatScaleLabel(Number.NaN), '—')
  assert.equal(formatScaleLabel(Number.POSITIVE_INFINITY), '—')
})

// Codex review 3 of 2026-10-09: decimals chosen from one value's magnitude print
// both ends of a narrow range as the same number — a scale that reads as zero-width.
test('scaleDecimals: enough decimals that the two ends of a range read differently', () => {
  const d = scaleDecimals(0.2231, 0.2234)
  assert.deepEqual([formatScaleLabel(0.2231, d), formatScaleLabel(0.2234, d)], ['0.2231', '0.2234'])
  const tiny = scaleDecimals(-0.0004, 0.0004)
  assert.deepEqual([formatScaleLabel(-0.0004, tiny), formatScaleLabel(0, tiny), formatScaleLabel(0.0004, tiny)], ['-0.0004', '0', '0.0004'])
})

test('scaleDecimals: an ordinary range keeps the magnitude rule, and a flat one does not loop', () => {
  assert.equal(scaleDecimals(-0.3, 0.3), 3)
  assert.equal(scaleDecimals(12.3, 45.1), 1)
  assert.equal(scaleDecimals(100, 250), 0)
  assert.equal(scaleDecimals(5, 5), 2)
  assert.equal(scaleDecimals(Number.NaN, 1), 2)
})
