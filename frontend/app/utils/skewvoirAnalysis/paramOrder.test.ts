import { test } from 'node:test'
import assert from 'node:assert/strict'
import { UNNAMED_PARAM_LABEL, isNamedParam, namedParams, paramLabel, sortByRowMpOrder } from './paramOrder.ts'

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

test('isNamedParam: a real name is named, blank/whitespace is not', () => {
  assert.equal(isNamedParam('CD_TOP'), true)
  assert.equal(isNamedParam(''), false)
  assert.equal(isNamedParam('   '), false)
})

test('namedParams drops the unnamed dummy parameter and keeps the rest in order', () => {
  const items = [{ parameter: '' }, { parameter: 'CD_TOP' }, { parameter: 'CD_BOTTOM' }]
  assert.deepEqual(names(namedParams(items)), ['CD_TOP', 'CD_BOTTOM'])
})

test('namedParams is a no-op when every parameter is named', () => {
  const items = [{ parameter: 'CD_TOP' }, { parameter: 'CD_BOTTOM' }]
  assert.deepEqual(names(namedParams(items)), ['CD_TOP', 'CD_BOTTOM'])
})

// The reason the two helpers compose: the dummy settling MP is measured FIRST,
// so it sorts first and would otherwise become the default parameter. Filtering
// before sorting makes the default "the next coming parameter".
test('the dummy MP leads the mp order, so filtering it hands the default to the next param', () => {
  const items = [{ parameter: '' }, { parameter: 'CD_TOP' }, { parameter: 'SIDEWALL_ANGLE' }]
  const rows = [row('', 0, 1), row('CD_TOP', 1, 2), row('SIDEWALL_ANGLE', 2, 3)]

  // Unfiltered, the nameless dummy wins the first slot.
  assert.deepEqual(names(sortByRowMpOrder(items, rows)), ['', 'CD_TOP', 'SIDEWALL_ANGLE'])
  // Filtered, the first slot is the first real parameter.
  assert.deepEqual(names(sortByRowMpOrder(namedParams(items), rows)), ['CD_TOP', 'SIDEWALL_ANGLE'])
})

test('paramLabel renders a real name as itself', () => {
  assert.equal(paramLabel('CD_TOP'), 'CD_TOP')
})

test('paramLabel gives the unnamed MP a visible stand-in, never an empty chip', () => {
  assert.equal(paramLabel(''), UNNAMED_PARAM_LABEL)
  assert.notEqual(paramLabel(''), '')
})

test('the stand-in cannot be mistaken for a real parameter name', () => {
  // "DUMMY" is a real parameter name in office data, which is why the stand-in
  // is a placeholder rather than a word: a real DUMMY must render as itself and
  // stay distinguishable from the point that has no name at all.
  assert.equal(paramLabel('DUMMY'), 'DUMMY')
  assert.notEqual(paramLabel('DUMMY'), UNNAMED_PARAM_LABEL)
  assert.equal(isNamedParam('DUMMY'), true)
})

// The default-pick rule the composable applies: prefer the first NAMED param,
// but fall back to the unnamed one rather than to nothing.
const pickDefault = (params: string[]): string => {
  const named = params.filter(isNamedParam)
  return named[0] ?? params[0] ?? ''
}

test('default pick skips the leading unnamed MP', () => {
  assert.equal(pickDefault(['', 'CD_TOP', 'SIDEWALL_ANGLE']), 'CD_TOP')
})

test('default pick falls back to the unnamed MP when it is the only parameter', () => {
  assert.equal(pickDefault(['']), '')
})

test('default pick is unchanged when no unnamed MP is present', () => {
  assert.equal(pickDefault(['CD_TOP', 'CD_BOTTOM']), 'CD_TOP')
  assert.equal(pickDefault([]), '')
})
