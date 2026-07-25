import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseChipXY } from './waferChip.ts'

// NOTE — Position Stack (views/PositionStack.vue) and Measurement Points
// synthesize chip coordinates from the `chip_number` text via parseChipXY, a
// plain "x, y" GRID-string parse, rather than the physical wafer coordinate
// model (stage_coordinate in nm, wafer_size in mm — utils/waferGeometry.ts)
// that the Dashboard's RadiusChart uses. A later task that unifies the two
// coordinate sources should produce a visible diff here.

test('parseChipXY reads a signed "x, y" grid pair', () => {
  assert.deepEqual(parseChipXY('3, -2'), [3, -2])
  assert.deepEqual(parseChipXY('0,0'), [0, 0])
})

test('parseChipXY drops a malformed chip_number entirely rather than guessing a coordinate', () => {
  // Missing comma, or non-finite parts — dropped, never fallen back to any
  // physical coordinate.
  assert.equal(parseChipXY('not-a-coordinate'), null)
  assert.equal(parseChipXY('NaN, 1'), null)
  // A single token would leave y `undefined`, and Number.isNaN(undefined) is
  // false — the length check is what catches it.
  assert.equal(parseChipXY('3'), null)
  assert.equal(parseChipXY('1, 2, 3'), null)
})
