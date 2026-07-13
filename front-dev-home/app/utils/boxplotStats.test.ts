// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { boxStats } from './boxplotStats.ts'

test('odd-length sample: exact median and R-7 interpolated quartiles', () => {
  assert.deepEqual(boxStats([1, 2, 3, 4, 5]), { min: 1, q1: 2, median: 3, q3: 4, max: 5 })
})

test('even-length sample: interpolated median and quartiles', () => {
  const s = boxStats([1, 2, 3, 4])!
  assert.equal(s.median, 2.5)
  assert.equal(s.q1, 1.75)
  assert.equal(s.q3, 3.25)
})

test('unsorted input is handled', () => {
  assert.equal(boxStats([5, 1, 4, 2, 3])!.median, 3)
})

test('single value collapses the box', () => {
  assert.deepEqual(
    boxStats([1.003]),
    { min: 1.003, q1: 1.003, median: 1.003, q3: 1.003, max: 1.003 }
  )
})

test('identical values collapse the box', () => {
  assert.deepEqual(boxStats([2, 2, 2]), { min: 2, q1: 2, median: 2, q3: 2, max: 2 })
})

test('non-finite values are dropped; empty input → null', () => {
  assert.equal(boxStats([]), null)
  assert.equal(boxStats([NaN, Infinity]), null)
  assert.equal(boxStats([NaN, 1, 3])!.median, 2)
})
