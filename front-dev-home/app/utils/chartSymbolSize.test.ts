// Pure-logic tests for chartSymbolSize. Run: node --test app/utils/chartSymbolSize.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { trendSymbolSize, UNMEASURED_SYMBOL } from './chartSymbolSize.ts'

test('no points or unmeasured host → the pre-measure default', () => {
  assert.equal(trendSymbolSize(500, 0), UNMEASURED_SYMBOL)
  assert.equal(trendSymbolSize(0, 120), UNMEASURED_SYMBOL)
})

test('a sparse series gets dots sized for the pointer', () => {
  // 12 BSM revisions across a full-width panel: ~68px apart, so the cap binds.
  assert.equal(trendSymbolSize(820, 12), 11)
  // 40 points across the same panel: ~20px apart, still capped.
  assert.equal(trendSymbolSize(820, 40), 11)
})

test('dots shrink as neighbours crowd, and never overlap', () => {
  // 100 points / 820px → 8.2px apart, so ~7px keeps the line visible between.
  assert.equal(trendSymbolSize(820, 100), 7)
  const spacing = 820 / 100
  assert.ok(trendSymbolSize(820, 100) < spacing, 'dot must fit its own share')
})

test('a quarter of BSM docs in a half-width pane floors at 5', () => {
  // The case that made a flat 9px bump fuse the series into a solid band:
  // 180 docs, ~207px of plot → 1.1px apart.
  assert.equal(trendSymbolSize(207, 180), 5)
  // Widening the pane does not lift it off the floor at this density.
  assert.equal(trendSymbolSize(807, 180), 5)
})

test('width and count both move the result — count alone is not enough', () => {
  // Same 120 points, two pane widths: the wide one can afford larger dots.
  assert.ok(trendSymbolSize(1600, 120) > trendSymbolSize(400, 120))
})
