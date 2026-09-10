// Pure-logic tests for afmHistogram. Run: node --test app/utils/afmHistogram.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  histogramStats,
  resolveBinCount,
  computeHistogram,
  normalCurveOverCenters,
  binIndexForValue
} from './afmHistogram.ts'

const approx = (a: number, b: number, eps = 1e-6) =>
  assert.ok(Math.abs(a - b) <= eps, `${a} ≈ ${b}`)

test('histogramStats: symmetric set', () => {
  const s = histogramStats([1, 2, 3, 4, 5])
  approx(s.mean, 3)
  approx(s.stdev, Math.sqrt(2))
  approx(s.q1, 2)
  approx(s.median, 3)
  approx(s.q3, 4)
  assert.equal(s.min, 1)
  assert.equal(s.max, 5)
  approx(s.skewness, 0)
  approx(s.cv, (Math.sqrt(2) / 3) * 100)
})

test('histogramStats: right-skewed → positive skewness', () => {
  assert.ok(histogramStats([1, 1, 1, 2, 10]).skewness > 0)
})

test('histogramStats: guards (N<3 skew 0, N<4 kurt 0, mean 0 cv 0, empty zeros)', () => {
  assert.equal(histogramStats([1, 2]).skewness, 0)
  assert.equal(histogramStats([1, 2, 3]).kurtosis, 0)
  assert.equal(histogramStats([-1, 1]).cv, 0)
  assert.deepEqual(histogramStats([]).count, 0)
})

test('resolveBinCount: custom clamps to [5,200]', () => {
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', 500), 200)
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', 2), 5)
  assert.equal(resolveBinCount([1, 2, 3, 4], 'custom', NaN), 5)
})

test('resolveBinCount: auto Sturges for outlier-free data', () => {
  const uniform = Array.from({ length: 100 }, (_, i) => i)
  // Sturges = ceil(1 + log2(100)) = 8; uniform has no >3σ outliers → Sturges.
  assert.equal(resolveBinCount(uniform, 'auto', 30), 8)
})

test('resolveBinCount: empty → 5', () => {
  assert.equal(resolveBinCount([], 'auto', 30), 5)
})

test('computeHistogram: frequency counts sum to N', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'frequency')
  assert.equal(h.values.reduce((a, b) => a + b, 0), 10)
  assert.equal(h.centers.length, 5)
  assert.equal(h.edges.length, 6)
})

test('computeHistogram: density integrates to ~1', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'density')
  const integral = h.values.reduce((a, v) => a + v * h.binWidth, 0)
  approx(integral, 1, 1e-9)
})

test('computeHistogram: cumulative is monotonic ending at N', () => {
  const h = computeHistogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 'cumulative')
  for (let i = 1; i < h.values.length; i++) assert.ok(h.values[i]! >= h.values[i - 1]!)
  assert.equal(h.values[h.values.length - 1], 10)
})

test('computeHistogram: zero span → single bin holding all', () => {
  const h = computeHistogram([5, 5, 5], 4, 'frequency')
  assert.deepEqual(h.centers, [5])
  assert.deepEqual(h.values, [3])
})

test('computeHistogram: empty → single zero bin', () => {
  const h = computeHistogram([], 5, 'frequency')
  assert.equal(h.values.length, 1)
  assert.equal(h.values[0], 0)
})

test('normalCurveOverCenters: empty when stdev 0, else one y per center peaking near mean', () => {
  const flat = histogramStats([5, 5, 5, 5])
  assert.deepEqual(normalCurveOverCenters(flat, 'density', 1, [5]), [])
  const s = histogramStats([1, 2, 3, 4, 5])
  const centers = [1, 2, 3, 4, 5]
  const ys = normalCurveOverCenters(s, 'density', 1, centers)
  assert.equal(ys.length, 5)
  const peak = ys.indexOf(Math.max(...ys))
  assert.equal(centers[peak], 3) // peak at the mean
})

test('binIndexForValue: locates the containing bin, clamps out-of-range', () => {
  const edges = [0, 2, 4, 6] // bins [0,2),[2,4),[4,6]
  assert.equal(binIndexForValue(edges, 1), 0)
  assert.equal(binIndexForValue(edges, 3), 1)
  assert.equal(binIndexForValue(edges, 6), 2)
  assert.equal(binIndexForValue(edges, -5), 0)
  assert.equal(binIndexForValue(edges, 99), 2)
})
