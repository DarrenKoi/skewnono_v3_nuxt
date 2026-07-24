// Pure-logic tests for tableCursor. Run: node --test app/utils/tableCursor.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nextCursorIndex } from './tableCursor.ts'

test('empty list is a no-op for every key', () => {
  for (const k of ['ArrowDown', 'ArrowUp', 'Home', 'End'] as const) {
    assert.equal(nextCursorIndex(k, 0, 0), null)
    assert.equal(nextCursorIndex(k, -1, 0), null)
  }
})

test('no row focused yet: Down → first, Up → last', () => {
  assert.equal(nextCursorIndex('ArrowDown', -1, 5), 0)
  assert.equal(nextCursorIndex('ArrowUp', -1, 5), 4)
})

test('arrows step by one and clamp at the edges (no wrap)', () => {
  assert.equal(nextCursorIndex('ArrowDown', 2, 5), 3)
  assert.equal(nextCursorIndex('ArrowDown', 4, 5), 4) // clamped at last
  assert.equal(nextCursorIndex('ArrowUp', 2, 5), 1)
  assert.equal(nextCursorIndex('ArrowUp', 0, 5), 0) // clamped at first
})

test('Home/End jump to the ends', () => {
  assert.equal(nextCursorIndex('Home', 3, 5), 0)
  assert.equal(nextCursorIndex('End', 1, 5), 4)
})

test('an out-of-range current index is treated as unfocused', () => {
  assert.equal(nextCursorIndex('ArrowDown', 9, 5), 0)
  assert.equal(nextCursorIndex('ArrowUp', 9, 5), 4)
})
