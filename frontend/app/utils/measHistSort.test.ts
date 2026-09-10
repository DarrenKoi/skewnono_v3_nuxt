import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DEFAULT_MEAS_HIST_SORT,
  isReordered,
  nextMeasHistSort,
  sortMeasHistRows,
  type SortableMeasHistRow
} from './measHistSort.ts'

const row = (
  msr: string,
  full_name: string,
  eqp_id: string,
  lot_id: string,
  timestamp: string
): SortableMeasHistRow => ({ msr, full_name, eqp_id, lot_id, timestamp })

const rows: SortableMeasHistRow[] = [
  row('m3', 'ADI/ADI_CD_BIAS_001', 'ECDX285', 'KPB266344', '2026-05-09T18:29:00Z'),
  row('m1', 'EDGE/EDGE_PROFILE_SCAN', 'ACD153', '4MJ248348', '2026-05-09T07:48:00Z'),
  row('m2', 'CNT/CNT_HOLE_001', 'VCD690', 'MJD257244', '2026-05-09T17:16:00Z')
]

const names = (sorted: SortableMeasHistRow[]) => sorted.map(r => r.msr)

test('default sort is newest first — the order the backend already returned', () => {
  assert.deepEqual(DEFAULT_MEAS_HIST_SORT, { key: 'timestamp', dir: 'desc' })
  assert.deepEqual(names(sortMeasHistRows(rows, DEFAULT_MEAS_HIST_SORT)), ['m3', 'm2', 'm1'])
})

test('sorts by recipe on the displayed full_name, not recipe_name', () => {
  // Displayed text is CLASS/RECIPE, so ADI/… precedes CNT/… precedes EDGE/….
  // Sorting the bare recipe_name would order these EDGE_… < ADI_… differently
  // from what the column shows.
  assert.deepEqual(names(sortMeasHistRows(rows, { key: 'recipe', dir: 'asc' })), ['m3', 'm2', 'm1'])
})

test('sorts by eqp_id and lot_id in both directions', () => {
  assert.deepEqual(names(sortMeasHistRows(rows, { key: 'eq', dir: 'asc' })), ['m1', 'm3', 'm2'])
  assert.deepEqual(names(sortMeasHistRows(rows, { key: 'eq', dir: 'desc' })), ['m2', 'm3', 'm1'])
  assert.deepEqual(names(sortMeasHistRows(rows, { key: 'lot', dir: 'asc' })), ['m1', 'm3', 'm2'])
})

test('ties break on msr so equal keys never reorder between renders', () => {
  // Three runs of ONE recipe — the exact case a user building a Time-Series set
  // is looking at, and the case where an unstable sort is most visible.
  const sameRecipe = [
    row('20260509_C', 'ADI/SAME', 'ECDX285', 'L1', '2026-05-09T01:00:00Z'),
    row('20260509_A', 'ADI/SAME', 'ECDX285', 'L2', '2026-05-09T02:00:00Z'),
    row('20260509_B', 'ADI/SAME', 'ECDX285', 'L3', '2026-05-09T03:00:00Z')
  ]
  const once = names(sortMeasHistRows(sameRecipe, { key: 'recipe', dir: 'asc' }))
  const twice = names(sortMeasHistRows([...sameRecipe].reverse(), { key: 'recipe', dir: 'asc' }))
  assert.deepEqual(once, ['20260509_A', '20260509_B', '20260509_C'])
  assert.deepEqual(once, twice, 'input order leaked into the result')
})

test('never mutates the caller array — it is shared SPA session state', () => {
  const original = [...rows]
  sortMeasHistRows(rows, { key: 'eq', dir: 'asc' })
  assert.deepEqual(rows, original)
})

test('an unknown sort key falls back to timestamp rather than throwing', () => {
  // Guards the useState-backed sort surviving a code change that drops a key.
  const bogus = { key: 'nope' as never, dir: 'desc' as const }
  assert.deepEqual(names(sortMeasHistRows(rows, bogus)), ['m3', 'm2', 'm1'])
})

test('clicking a new column picks a sensible first direction', () => {
  // Newest-first for time; A→Z for the text columns.
  assert.deepEqual(nextMeasHistSort({ key: 'recipe', dir: 'asc' }, 'timestamp'), { key: 'timestamp', dir: 'desc' })
  assert.deepEqual(nextMeasHistSort(DEFAULT_MEAS_HIST_SORT, 'recipe'), { key: 'recipe', dir: 'asc' })
  assert.deepEqual(nextMeasHistSort(DEFAULT_MEAS_HIST_SORT, 'lot'), { key: 'lot', dir: 'asc' })
})

test('clicking the active column flips its direction', () => {
  assert.deepEqual(nextMeasHistSort({ key: 'eq', dir: 'asc' }, 'eq'), { key: 'eq', dir: 'desc' })
  assert.deepEqual(nextMeasHistSort({ key: 'eq', dir: 'desc' }, 'eq'), { key: 'eq', dir: 'asc' })
})

test('isReordered only fires once the order leaves the backend default', () => {
  assert.equal(isReordered(DEFAULT_MEAS_HIST_SORT), false)
  assert.equal(isReordered({ key: 'timestamp', dir: 'asc' }), true)
  assert.equal(isReordered({ key: 'recipe', dir: 'asc' }), true)
})
