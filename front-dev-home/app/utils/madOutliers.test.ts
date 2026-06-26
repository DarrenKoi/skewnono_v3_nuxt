// Pure-logic tests for madOutliers. Run: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectMadOutliers, MAD_DEFAULT_K, MAD_DEFAULT_MIN_N } from './madOutliers.ts'

test('empty array → empty result', () => {
  assert.deepEqual(detectMadOutliers([]), [])
})

test('below minN → all false (length preserved)', () => {
  assert.deepEqual(detectMadOutliers([1, 2, 100, 3]), [false, false, false, false])
})

test('clean series at/above minN → no outliers', () => {
  assert.deepEqual(
    detectMadOutliers([10, 11, 9, 10, 12, 8]),
    [false, false, false, false, false, false]
  )
})

test('single clear outlier is flagged, others are not', () => {
  const flags = detectMadOutliers([10, 10, 11, 9, 10, 80])
  assert.deepEqual(flags, [false, false, false, false, false, true])
})

test('all-identical values (MAD=0) → no false positives', () => {
  assert.deepEqual(detectMadOutliers([7, 7, 7, 7, 7]), [false, false, false, false, false])
})

test('MAD=0 with one different value → only the different one flags', () => {
  // median 7, MAD 0 → fall back to "differs from median".
  const flags = detectMadOutliers([7, 7, 7, 7, 7, 9])
  assert.deepEqual(flags, [false, false, false, false, false, true])
})

test('masking: a single extreme does not hide itself (vs classic z-score)', () => {
  // Tight cluster + one far value; classic mean±std would inflate std and miss it.
  const flags = detectMadOutliers([50, 51, 49, 50, 52, 48, 500])
  assert.equal(flags[6], true)
  assert.equal(flags.slice(0, 6).some(Boolean), false)
})

test('k is configurable (looser k flags fewer)', () => {
  const values = [10, 10, 11, 9, 10, 20]
  const strict = detectMadOutliers(values, 3.5)
  const loose = detectMadOutliers(values, 100)
  assert.equal(strict[5], true)
  assert.equal(loose.some(Boolean), false)
})

test('exported defaults', () => {
  assert.equal(MAD_DEFAULT_K, 3.5)
  assert.equal(MAD_DEFAULT_MIN_N, 5)
})
