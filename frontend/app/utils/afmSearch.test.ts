// Pure-logic tests for afmSearch. Run: node --test app/utils/afmSearch.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmMeasurement } from '~/composables/useAfmCart'
import { dateWindow, filterMeasurements } from './afmSearch.ts'

const row = (recipeName: string, lotId: string, formattedDate: string): AfmMeasurement => ({
  filename: `#${formattedDate}#${recipeName}#${lotId}#.csv`,
  recipeName,
  lotId,
  slotNumber: '01',
  measuredInfo: 'standard',
  formattedDate
})

const rows = [
  row('CMP_POST', 'T7HQR16', '2026-04-24 09:30:00'),
  row('ETCH_TRIM', 'T3HQR17', '2026-04-23 08:30:00'),
  row('CMP_POST', 'CRAP119', '2026-04-22'),
  row('ETCH_TRIM', 'T7HQR1A', '2026-04-13 08:30:00')
]
const today = '2026-04-24'
const all = { terms: [], recipes: [], lot: '', days: null, today }

test('dateWindow: a preset counts back from today; no preset is the span of the list', () => {
  assert.deepEqual(dateWindow(rows, null, today), ['2026-04-13', '2026-04-24'])
  assert.deepEqual(dateWindow(rows, 1, today), ['2026-04-24', '2026-04-24'])
  assert.deepEqual(dateWindow(rows, 3, today), ['2026-04-22', '2026-04-24'])
  // A tool that last measured days ago: the window is still today's.
  assert.deepEqual(dateWindow(rows, 3, '2026-05-01'), ['2026-04-29', '2026-05-01'])
  assert.deepEqual(dateWindow([], 3, today), ['2026-04-22', '2026-04-24'])
  assert.equal(dateWindow([], null, today), null)
})

test('filterMeasurements: each filter narrows, and they combine', () => {
  assert.equal(filterMeasurements(rows, all).length, 4)
  assert.equal(filterMeasurements(rows, { ...all, days: 1 }).length, 1)
  assert.equal(filterMeasurements(rows, { ...all, days: 3 }).length, 3)
  assert.equal(filterMeasurements(rows, { ...all, recipes: ['ETCH_TRIM'] }).length, 2)
  assert.equal(filterMeasurements(rows, { ...all, lot: 't7hqr' }).length, 2)
  assert.equal(filterMeasurements(rows, { ...all, terms: ['cmp', ' '] }).length, 2)
  assert.deepEqual(
    filterMeasurements(rows, { ...all, terms: ['t7'], recipes: ['ETCH_TRIM'] }).map(r => r.lotId),
    ['T7HQR1A']
  )
  assert.deepEqual(filterMeasurements([], { ...all, days: 3 }), [])
  // A row with no date or lot stays in 전체, leaves a dated window, and breaks nothing.
  const odd = [...rows, { ...row('CMP_POST', 'X', ''), formattedDate: null, lotId: null } as unknown as AfmMeasurement]
  assert.equal(filterMeasurements(odd, { ...all, terms: ['cmp'] }).length, 3)
  assert.equal(filterMeasurements(odd, { ...all, days: 7, lot: 't7' }).length, 1)
  assert.deepEqual(dateWindow(odd, null, today), ['2026-04-13', '2026-04-24'])
  // Nothing measured today: "오늘" is empty, it does not fall back to the newest day.
  assert.deepEqual(filterMeasurements(rows, { ...all, days: 1, today: '2026-04-25' }), [])
})
