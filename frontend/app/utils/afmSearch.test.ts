// Pure-logic tests for afmSearch. Run: node --test app/utils/afmSearch.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmMeasurement } from '~/composables/useAfmCart'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { dateWindow, filterMeasurements, toMeasurement } from './afmSearch.ts'

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
  // A row with no date stays in 전체 and leaves every dated window.
  const undated = [...rows, row('CMP_POST', 'X', '')]
  assert.equal(filterMeasurements(undated, { ...all, terms: ['cmp'] }).length, 3)
  assert.equal(filterMeasurements(undated, { ...all, days: 30 }).length, 4)
  assert.deepEqual(dateWindow(undated, null, today), ['2026-04-13', '2026-04-24'])
  // Nothing measured today: "오늘" is empty, it does not fall back to the newest day.
  assert.deepEqual(filterMeasurements(rows, { ...all, days: 1, today: '2026-04-25' }), [])
})

test('toMeasurement: folds the time into the date; a missing cell becomes an empty string', () => {
  const full = toMeasurement({
    filename: 'a.csv', recipe_name: 'CMP_POST', lot_id: 'T7HQR16', slot_number: '01',
    measured_info: 'standard', formatted_date: '2026-04-24', time: '0930', has_data: true
  })
  assert.equal(full.formattedDate, '2026-04-24 09:30:00')
  assert.equal(full.hasData, true)
  // What an office row might leave out, however the type reads.
  const bare = toMeasurement({ filename: 'b.csv', time: '093000' } as AfmFileRow)
  assert.deepEqual(
    [bare.recipeName, bare.lotId, bare.slotNumber, bare.measuredInfo, bare.formattedDate],
    ['', '', '', '', '']
  )
  assert.deepEqual(filterMeasurements([full, bare], { ...all, terms: ['cmp'], lot: 't7' }), [full])
})
