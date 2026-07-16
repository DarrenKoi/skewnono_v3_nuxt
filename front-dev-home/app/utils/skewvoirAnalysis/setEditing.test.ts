import { test } from 'node:test'
import assert from 'node:assert/strict'
import { removeFromSet, clearToFocus, ensureFocus } from './setEditing.ts'

test('removeFromSet drops the given msr and preserves order', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b', 'c'], 'b', 'a'),
    ['a', 'c']
  )
})

test('removeFromSet never drops the focused msr (guard)', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b', 'c'], 'a', 'a'),
    ['a', 'b', 'c']
  )
})

test('removeFromSet is a no-op when msr is absent', () => {
  assert.deepEqual(
    removeFromSet(['a', 'b'], 'z', 'a'),
    ['a', 'b']
  )
})

test('removeFromSet returns a new array (no mutation)', () => {
  const input = ['a', 'b']
  const out = removeFromSet(input, 'b', 'a')
  assert.notEqual(out, input)
  assert.deepEqual(input, ['a', 'b'])
})

test('clearToFocus returns just the focused msr', () => {
  assert.deepEqual(clearToFocus('b'), ['b'])
})

test('ensureFocus re-adds the focused msr when it was deselected', () => {
  assert.deepEqual(ensureFocus(['a', 'b'], 'c'), ['c', 'a', 'b'])
})

test('ensureFocus leaves the list unchanged when focus is present', () => {
  assert.deepEqual(ensureFocus(['a', 'b'], 'a'), ['a', 'b'])
})

test('ensureFocus with empty focus returns a copy unchanged', () => {
  assert.deepEqual(ensureFocus(['a', 'b'], ''), ['a', 'b'])
})

test('ensureFocus returns a new array (no mutation)', () => {
  const input = ['a', 'b']
  assert.notEqual(ensureFocus(input, 'a'), input)
})
