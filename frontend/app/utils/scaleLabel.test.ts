// Run: cd frontend && node --test app/utils/scaleLabel.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatScaleLabel, scaleFormatter } from './scaleLabel.ts'

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

// Codex review 3 of 2026-10-09 (both passes): one formatter for a whole scale.
// Chosen per value, 0.2231 and 0.2234 both print "0.223" and a scale with width
// reads as flat; chosen from the larger end alone, 0.25 … 100 prints "0 … 100".
test('scaleFormatter: the two ends of a narrow range read differently', () => {
  const f = scaleFormatter(0.2231, 0.2234)
  assert.deepEqual([f(0.2231), f(0.2234)], ['0.2231', '0.2234'])
  const tiny = scaleFormatter(-0.0004, 0.0004)
  assert.deepEqual([tiny(-0.0004), tiny(0), tiny(0.0004)], ['-0.0004', '0', '0.0004'])
})

test('scaleFormatter: the smaller end keeps the decimals its own magnitude needs', () => {
  const f = scaleFormatter(0.25, 100)
  assert.deepEqual([f(0.25), f(100)], ['0.25', '100'])
  // An exact zero end asks for no decimals of its own.
  const z = scaleFormatter(0, 45.126)
  assert.deepEqual([z(0), z(45.126)], ['0', '45.1'])
})

test('scaleFormatter: past eight decimals it switches to exponent form rather than collide', () => {
  const f = scaleFormatter(0.2231000001, 0.2231000004)
  assert.deepEqual([f(0.2231000001), f(0.2231000004)], ['2.231000001e-1', '2.231000004e-1'])
  const nano = scaleFormatter(1e-9, 4e-9)
  assert.deepEqual([nano(1e-9), nano(4e-9)], ['1e-9', '4e-9'])
})

test('scaleFormatter: an ordinary range keeps the magnitude rule; flat and non-finite ranges do not loop', () => {
  const f = scaleFormatter(-0.3, 0.3)
  assert.deepEqual([f(-0.3), f(0), f(0.3)], ['-0.3', '0', '0.3'])
  assert.equal(scaleFormatter(12.3, 45.1)(22.56), '22.6')
  assert.equal(scaleFormatter(100, 250)(175.4), '175')
  assert.equal(scaleFormatter(5, 5)(5), '5')
  assert.equal(scaleFormatter(Number.NaN, 1)(0.5), '0.5')
  assert.equal(scaleFormatter(0, 1)(Number.NaN), '—')
})

// Codex review 3, third pass: fifteen exponent digits still cannot tell two
// adjacent doubles apart. Past that, the number's own round-trip string does.
test('scaleFormatter: adjacent doubles still read differently', () => {
  const max = 1 + Number.EPSILON
  const f = scaleFormatter(1, max)
  assert.deepEqual([f(1), f(max)], ['1', '1.0000000000000002'])
})
