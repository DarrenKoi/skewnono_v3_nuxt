// Pure-logic tests for chartRange. Run: node --test app/utils/chartRange.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { stableYRange, stableRadialRange } from './chartRange.ts'

test('empty or all-NaN input → null (caller falls back to scale:true)', () => {
  assert.equal(stableYRange([]), null)
  assert.equal(stableYRange([NaN, Infinity, -Infinity]), null)
})

test('stable data around a large value gets a magnitude-relative span', () => {
  // ±0.1 wobble around 100 → span must be ≥ 25% of magnitude, not 0.2.
  const r = stableYRange([99.9, 100.05, 99.95, 100.1, 100.0])
  assert.ok(r)
  assert.ok(r.max - r.min >= 25, `span ${r.max - r.min} should be ≥ 25`)
  assert.ok(r.min <= 99.9 && r.max >= 100.1, 'data stays inside the range')
})

test('genuinely varying data keeps a padded data-driven span', () => {
  const r = stableYRange([0, 25, 50, 75, 100])
  assert.ok(r)
  assert.ok(r.min <= 0 && r.max >= 100, 'data stays inside the range')
  assert.ok(r.max - r.min <= 100 * 1.6, 'span stays close to the data span')
})

test('constant series still produces a non-degenerate range', () => {
  const r = stableYRange([23.4, 23.4, 23.4])
  assert.ok(r)
  assert.ok(r.min < 23.4 && r.max > 23.4)
  assert.ok(r.max - r.min >= 23.4 * 0.25 * 0.99)
})

test('all-zero series → fixed [-1, 1]', () => {
  assert.deepEqual(stableYRange([0, 0, 0]), { min: -1, max: 1, interval: 0.5 })
})

test('negative stable values work the same way', () => {
  const r = stableYRange([-49.9, -50.1, -50.0])
  assert.ok(r)
  assert.ok(r.min <= -50.1 && r.max >= -49.9)
  assert.ok(r.max - r.min >= 12.5, 'span ≥ 25% of |−50|')
})

test('NaN entries are ignored, not poisoning the range', () => {
  const withNaN = stableYRange([99.9, NaN, 100.1, NaN])
  const clean = stableYRange([99.9, 100.1])
  assert.deepEqual(withNaN, clean)
})

test('bounds land on interval multiples so ticks are round', () => {
  const r = stableYRange([99.9, 100.1])
  assert.ok(r)
  const spanSteps = (r.max - r.min) / r.interval
  assert.ok(Math.abs(spanSteps - Math.round(spanSteps)) < 1e-9, `span ${r.max - r.min} not a multiple of ${r.interval}`)
  const minSteps = r.min / r.interval
  assert.ok(Math.abs(minSteps - Math.round(minSteps)) < 1e-9, `min ${r.min} not aligned to ${r.interval}`)
})

test('zeroMin anchors non-negative metrics at 0 with 2× headroom', () => {
  const r = stableYRange([0.02, 0.1, 0.05], { zeroMin: true })
  assert.ok(r)
  assert.equal(r.min, 0)
  assert.ok(r.max >= 0.2, `max ${r.max} should leave 2× headroom over 0.1`)
  const steps = r.max / r.interval
  assert.ok(Math.abs(steps - Math.round(steps)) < 1e-9, 'max aligned to interval')
})

test('zeroMin is ignored when values go negative', () => {
  const withOpt = stableYRange([-0.05, 0.1], { zeroMin: true })
  const without = stableYRange([-0.05, 0.1])
  assert.deepEqual(withOpt, without)
})

test('zeroMin with all-zero values → fixed [0, 1]', () => {
  assert.deepEqual(stableYRange([0, 0], { zeroMin: true }), { min: 0, max: 1, interval: 0.2 })
})

test('tiny magnitudes (near-zero deltas) do not collapse or explode', () => {
  const r = stableYRange([0.0021, 0.0019, 0.002])
  assert.ok(r)
  assert.ok(r.min <= 0.0019 && r.max >= 0.0021)
  assert.ok(r.max - r.min < 0.01, 'range stays in the data’s order of magnitude')
})

test('stableRadialRange: same stable bounds as stableYRange, min/max only', () => {
  const y = stableYRange([99.9, 100.1, 100.0])
  const r = stableRadialRange([99.9, 100.1, 100.0])
  assert.ok(y && r)
  assert.deepEqual(r, { min: y.min, max: y.max })
  assert.ok(!('interval' in r))
})

test('stableRadialRange: empty input → null (caller falls back)', () => {
  assert.equal(stableRadialRange([NaN]), null)
})
