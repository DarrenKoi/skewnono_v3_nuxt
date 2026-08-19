import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clearToFocus, ensureFocus } from './setEditing.ts'

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
