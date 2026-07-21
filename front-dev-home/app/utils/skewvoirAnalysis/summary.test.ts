import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatSelectionSummary } from './summary.ts'

const sel = {
  lot: 'LOT123',
  recipe: 'RCP_A',
  eq: 'EQ12',
  mp: 'MP_01',
  msr: 'M-9001',
  capturedAt: '2026-07-21 10:00'
}

test('formatSelectionSummary lists every field with the share link last', () => {
  assert.equal(
    formatSelectionSummary(sel, 'CD_BOTTOM', 'http://sknn/link'),
    [
      'MSR: M-9001',
      'Param: CD_BOTTOM',
      'Lot: LOT123',
      'Recipe: RCP_A',
      'EQ: EQ12',
      'MP: MP_01',
      'Captured: 2026-07-21 10:00',
      'Link: http://sknn/link'
    ].join('\n')
  )
})

test('formatSelectionSummary drops empty fields instead of printing placeholders', () => {
  const out = formatSelectionSummary({ ...sel, recipe: '', capturedAt: '' }, '', 'http://sknn/link')
  assert.equal(
    out,
    ['MSR: M-9001', 'Lot: LOT123', 'EQ: EQ12', 'MP: MP_01', 'Link: http://sknn/link'].join('\n')
  )
  assert.ok(!out.includes('—'))
})

test('formatSelectionSummary with no share url still summarizes the facts', () => {
  const out = formatSelectionSummary(sel, 'CD_BOTTOM', '')
  assert.ok(out.startsWith('MSR: M-9001'))
  assert.ok(!out.includes('Link:'))
})
