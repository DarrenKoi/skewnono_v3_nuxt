import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sortByRowMpOrder } from './paramOrder.ts'

const row = (parameter: string, mp_number: number, sequence: number) =>
  ({ parameter, mp_number, sequence })

const names = (items: { parameter: string }[]) => items.map(i => i.parameter)

test('orders parameters by their lowest mp_number', () => {
  const items = [{ parameter: 'C' }, { parameter: 'A' }, { parameter: 'B' }]
  const rows = [row('A', 3, 1), row('B', 1, 2), row('C', 2, 3)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['B', 'C', 'A'])
})

test('breaks mp_number ties by sequence', () => {
  const items = [{ parameter: 'A' }, { parameter: 'B' }]
  const rows = [row('A', 1, 9), row('B', 1, 2)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['B', 'A'])
})

test('uses the minimum rank across a parameter\'s rows, not the first row', () => {
  const items = [{ parameter: 'A' }, { parameter: 'B' }]
  const rows = [row('A', 5, 1), row('B', 4, 2), row('A', 2, 3)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['A', 'B'])
})

test('negative mp_number sentinels lose to measured mp_numbers', () => {
  const items = [{ parameter: 'A' }, { parameter: 'B' }]
  // A has a sentinel row that would win a naive min; its real MP is 7.
  const rows = [row('A', -1, 1), row('A', 7, 2), row('B', 3, 3)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['B', 'A'])
})

test('a parameter with only sentinel rows still ranks (after measured ones)', () => {
  const items = [{ parameter: 'A' }, { parameter: 'B' }]
  const rows = [row('A', -1, 1), row('B', 9, 2)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['B', 'A'])
})

test('parameters absent from rows keep incoming order at the end', () => {
  const items = [{ parameter: 'X' }, { parameter: 'A' }, { parameter: 'Y' }]
  const rows = [row('A', 1, 1)]
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['A', 'X', 'Y'])
})

test('empty rows leave the incoming order untouched', () => {
  const items = [{ parameter: 'B' }, { parameter: 'A' }]
  assert.deepEqual(names(sortByRowMpOrder(items, [])), ['B', 'A'])
})
