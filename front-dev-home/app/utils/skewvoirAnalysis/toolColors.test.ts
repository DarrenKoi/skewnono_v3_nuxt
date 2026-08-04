import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rankToolColors, toolLegendChips, TOOL_COLOR_LIMIT } from './toolColors.ts'
import { SK_SITE, SK_SITE_OVERFLOW } from '../chartPalette.ts'

test('rankToolColors gives identity colors by contribution count, ties by id', () => {
  // TP02 contributed 2 items → first color; TP01/TP03 tie at 1 → id order.
  const map = rankToolColors(['TP03', 'TP02', 'TP01', 'TP02'])
  assert.equal(map.get('TP02'), SK_SITE[0])
  assert.equal(map.get('TP01'), SK_SITE[1])
  assert.equal(map.get('TP03'), SK_SITE[2])
})

test('rankToolColors collapses tools past the palette cap into the overflow neutral', () => {
  const ids = Array.from({ length: TOOL_COLOR_LIMIT + 3 }, (_, i) => `T${String(i).padStart(2, '0')}`)
  const map = rankToolColors(ids)
  const overflow = [...map.values()].filter(c => c === SK_SITE_OVERFLOW)
  assert.equal(overflow.length, 3)
})

test('toolLegendChips folds every overflow tool into ONE labelled 기타 chip', () => {
  const ids = Array.from({ length: TOOL_COLOR_LIMIT + 2 }, (_, i) => `T${String(i).padStart(2, '0')}`)
  const chips = toolLegendChips(rankToolColors(ids))
  assert.equal(chips.length, TOOL_COLOR_LIMIT + 1)
  assert.deepEqual(chips.at(-1), { label: '기타 (2)', color: SK_SITE_OVERFLOW })
})

test('toolLegendChips with few tools has no 기타 chip', () => {
  const chips = toolLegendChips(rankToolColors(['A', 'B']))
  assert.deepEqual(chips.map(c => c.label), ['A', 'B'])
})
