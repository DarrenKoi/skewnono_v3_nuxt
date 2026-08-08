import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rankToolColors, toolLegendChips, TOOL_COLOR_LIMIT, TOOL_PALETTE } from './toolColors.ts'
import { SK_SITE, SK_SITE_OVERFLOW, SK_STATE } from '../chartPalette.ts'

test('rankToolColors gives identity colors by contribution count, ties by id', () => {
  // TP02 contributed 2 items → first color; TP01/TP03 tie at 1 → id order.
  const map = rankToolColors(['TP03', 'TP02', 'TP01', 'TP02'])
  assert.equal(map.get('TP02'), TOOL_PALETTE[0])
  assert.equal(map.get('TP01'), TOOL_PALETTE[1])
  assert.equal(map.get('TP03'), TOOL_PALETTE[2])
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

// The regression this file exists to prevent. Tool identity and anomaly severity
// are two legends over ONE set of marks, so an identity color that equals a
// severity color makes the chart lie in a way no amount of legend text repairs.
// Asserted over every color the ranker can actually hand out — including the
// overflow neutral, which sits next to the 미평가 swatch.
test('no color rankToolColors can emit is a severity color', () => {
  const ids = Array.from({ length: TOOL_COLOR_LIMIT + 5 }, (_, i) => `T${String(i).padStart(2, '0')}`)
  const emitted = new Set(rankToolColors(ids).values())
  for (const severity of Object.values(SK_STATE)) {
    assert.ok(
      !emitted.has(severity),
      `identity palette emits ${severity}, which is a SK_STATE severity color`
    )
  }
})

// The identity palette is a SUBSET of SK_SITE, never a parallel invention — one
// tool must not wear a different color here than it wears on the wafer map.
test('every identity color is an SK_SITE color', () => {
  assert.ok(TOOL_PALETTE.length > 0)
  assert.equal(TOOL_COLOR_LIMIT, TOOL_PALETTE.length)
  for (const color of TOOL_PALETTE) {
    assert.ok((SK_SITE as readonly string[]).includes(color), `${color} is not in SK_SITE`)
  }
})
