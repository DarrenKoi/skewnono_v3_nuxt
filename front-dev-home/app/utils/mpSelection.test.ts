// Pure-logic tests for mpSelection. Run: node --test app/utils/mpSelection.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toggleSeq, headerState, pickExportRows } from './mpSelection.ts'

test('toggleSeq adds a missing seq and removes a present one', () => {
  assert.deepEqual(toggleSeq([1, 2], 3), [1, 2, 3])
  assert.deepEqual(toggleSeq([1, 2, 3], 2), [1, 3])
})

test('toggleSeq returns a new array (no mutation)', () => {
  const src = [1, 2]
  const out = toggleSeq(src, 3)
  assert.deepEqual(src, [1, 2])
  assert.notEqual(out, src)
})

test('headerState reflects the visible rows only', () => {
  assert.equal(headerState([], new Set([1])), 'none')
  assert.equal(headerState([1, 2, 3], new Set()), 'none')
  assert.equal(headerState([1, 2, 3], new Set([2])), 'some')
  assert.equal(headerState([1, 2, 3], new Set([1, 2, 3, 9])), 'all')
})

test('pickExportRows: empty selection → all rows; otherwise checked ∩ visible', () => {
  const rows = [{ seq: 1 }, { seq: 2 }, { seq: 3 }]
  assert.deepEqual(pickExportRows(rows, new Set()), rows)
  assert.deepEqual(pickExportRows(rows, new Set([2, 9])), [{ seq: 2 }])
})
