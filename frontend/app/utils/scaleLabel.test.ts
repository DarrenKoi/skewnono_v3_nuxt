// Run: cd frontend && node --test app/utils/scaleLabel.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatScaleLabel } from './scaleLabel.ts'

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
