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
const all = { terms: [], recipes: [], lot: '', days: null }

test('dateWindow: ends at the newest measurement, not at today', () => {
  assert.deepEqual(dateWindow(rows, null), ['2026-04-13', '2026-04-24'])
  assert.deepEqual(dateWindow(rows, 1), ['2026-04-24', '2026-04-24'])
  assert.deepEqual(dateWindow(rows, 3), ['2026-04-22', '2026-04-24'])
  assert.equal(dateWindow([], 3), null)
})

test('filterMeasurements: each filter narrows, and they combine', () => {
  assert.equal(filterMeasurements(rows, all).length, 4)
  assert.equal(filterMeasurements(rows, { ...all, days: 1 }).length, 1)
  assert.equal(filterMeasurements(rows, { ...all, days: 3 }).length, 3)
  assert.equal(filterMeasurements(rows, { ...all, recipes: ['ETCH_TRIM'] }).length, 2)
  assert.equal(filterMeasurements(rows, { ...all, lot: 't7hqr' }).length, 2)
  assert.equal(filterMeasurements(rows, { ...all, terms: ['cmp', ' '] }).length, 2)
  assert.deepEqual(
    filterMeasurements(rows, { terms: ['t7'], recipes: ['ETCH_TRIM'], lot: '', days: null }).map(r => r.lotId),
    ['T7HQR1A']
  )
  assert.deepEqual(filterMeasurements([], { ...all, days: 3 }), [])
})
