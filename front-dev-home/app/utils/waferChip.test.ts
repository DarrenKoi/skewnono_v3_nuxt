// Pure-logic tests for waferChip. Run: node --test app/utils/waferChip.test.ts
//
// `chip_number` is the DIE INDEX pair ("x, y") on the die grid — not a physical
// coordinate. Physical position comes from `stage_coordinate` (nm) via
// utils/waferGeometry.ts; parseChipXY is the cruder text parse used by Position
// Stack and the spatial helpers.
//
// So two coordinate sources coexist: views/PositionStack.vue and Measurement
// Points synthesize positions from this grid string, while the Dashboard's
// RadiusChart uses the physical model. A later task that unifies them should
// produce a visible diff in this file.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseChipXY } from './waferChip.ts'

test('parseChipXY reads a plain die-index pair', () => {
  assert.deepEqual(parseChipXY('22,26'), [22, 26])
  assert.deepEqual(parseChipXY('0,0'), [0, 0])
})

test('parseChipXY tolerates the spacing the backend actually emits', () => {
  assert.deepEqual(parseChipXY('3, -2'), [3, -2])
  assert.deepEqual(parseChipXY('  3 ,  -2  '), [3, -2])
})

test('parseChipXY keeps signs on both axes (indices are centre-relative)', () => {
  assert.deepEqual(parseChipXY('-5,7'), [-5, 7])
  assert.deepEqual(parseChipXY('5,-7'), [5, -7])
  assert.deepEqual(parseChipXY('-5,-7'), [-5, -7])
})

test('parseChipXY does not transpose the axes', () => {
  // Distinct values, so an x/y swap is caught here.
  assert.deepEqual(parseChipXY('1,2'), [1, 2])
  assert.deepEqual(parseChipXY('2,1'), [2, 1])
})

test('parseChipXY accepts a fractional index without rounding it', () => {
  // Not expected from the office schema, but the parser must not silently
  // truncate if it ever appears — the caller decides.
  assert.deepEqual(parseChipXY('1.5,-2.5'), [1.5, -2.5])
})

test('parseChipXY rejects anything that is not exactly two tokens', () => {
  assert.equal(parseChipXY(''), null)
  assert.equal(parseChipXY('12'), null)
  assert.equal(parseChipXY('not-a-coordinate'), null)
  assert.equal(parseChipXY('1,2,3'), null)
})

test('parseChipXY rejects non-finite tokens', () => {
  // Number.isNaN alone would not catch the y side: a missing second token
  // makes it `undefined`, hence the explicit length + finiteness checks.
  assert.equal(parseChipXY('NaN,1'), null)
  assert.equal(parseChipXY('1,NaN'), null)
  assert.equal(parseChipXY('abc,1'), null)
  assert.equal(parseChipXY('1,abc'), null)
  assert.equal(parseChipXY('Infinity,1'), null)
  assert.equal(parseChipXY('1,-Infinity'), null)
})

// KNOWN GAP: an empty token coerces to 0 because Number('') === 0, so a
// malformed-but-two-token chip_number lands on die (0,0) instead of being
// dropped. Harmless with the office data seen so far (always "x,y"), and pinned
// here so a later tightening of the parser produces a visible diff.
test('KNOWN GAP — a blank token is read as 0, not rejected', () => {
  assert.deepEqual(parseChipXY('1,'), [1, 0])
  assert.deepEqual(parseChipXY(','), [0, 0])
  assert.deepEqual(parseChipXY(' , '), [0, 0])
})
