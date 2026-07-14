// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mean, sampleStd, quantileSorted, iqrFences, pearson, spearman, linearFit } from './stats.ts'

const close = (a: number, b: number, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) < eps, `${a} !== ${b}`)

test('mean of empty is NaN, not 0 — an empty set has no centre', () => {
  assert.ok(Number.isNaN(mean([])))
})

test('sampleStd uses n-1 and is 0 for a single value', () => {
  close(sampleStd([2, 4, 4, 4, 5, 5, 7, 9]), 2.138089935299395)
  assert.equal(sampleStd([3]), 0)
  assert.equal(sampleStd([]), 0)
})

test('sampleStd is numerically stable for large offsets', () => {
  // The one-pass sumsq/n - m^2 shortcut loses all precision here and can go negative.
  close(sampleStd([1e9 + 4, 1e9 + 7, 1e9 + 13, 1e9 + 16]), 5.477225575051661, 1e-6)
})

test('quantileSorted matches R-7 / numpy default', () => {
  close(quantileSorted([1, 2, 3, 4], 0.25), 1.75)
  close(quantileSorted([1, 2, 3, 4], 0.5), 2.5)
  close(quantileSorted([1, 2, 3, 4], 0.75), 3.25)
})

test('iqrFences applies Tukey 1.5x IQR', () => {
  const f = iqrFences([1, 2, 3, 4, 5, 6, 7, 8, 9])!
  close(f.q1, 3)
  close(f.q3, 7)
  close(f.lower, 3 - 1.5 * 4)
  close(f.upper, 7 + 1.5 * 4)
})

test('iqrFences returns null on empty and ignores non-finite values', () => {
  assert.equal(iqrFences([]), null)
  close(iqrFences([1, Number.NaN, 2, 3, 4])!.q1, 1.75)
})

test('pearson is 1 for a perfect positive line and -1 for a negative one', () => {
  close(pearson([[1, 2], [2, 4], [3, 6], [4, 8]])!, 1)
  close(pearson([[1, -2], [2, -4], [3, -6], [4, -8]])!, -1)
})

test('pearson refuses n < 3 — at n=2 r is trivially +/-1', () => {
  assert.equal(pearson([[1, 5], [2, 9]]), null)
})

test('pearson returns null on zero variance in either axis', () => {
  assert.equal(pearson([[1, 5], [1, 7], [1, 9]]), null)
  assert.equal(pearson([[1, 5], [2, 5], [3, 5]]), null)
})

test('spearman is 1 for any monotonic relation, even a non-linear one', () => {
  // Pearson would NOT be 1 here; that is the whole reason Spearman exists.
  close(spearman([[1, 1], [2, 8], [3, 27], [4, 64]])!, 1)
})

test('spearman handles tied ranks with average ranks', () => {
  // x ranks: 1, 2.5, 2.5, 4 | y ranks: 1, 2.5, 2.5, 4 -> perfect agreement
  close(spearman([[10, 1], [20, 2], [20, 2], [30, 3]])!, 1)
})

test('linearFit recovers slope and intercept', () => {
  const fit = linearFit([[0, 1], [1, 3], [2, 5], [3, 7]])!
  close(fit.slope, 2)
  close(fit.intercept, 1)
})

test('linearFit returns null when x has zero variance', () => {
  assert.equal(linearFit([[2, 1], [2, 3], [2, 5]]), null)
})
