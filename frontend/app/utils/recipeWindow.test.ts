import { test } from 'node:test'
import assert from 'node:assert/strict'
import { recipeWindowRows, recipeWindowSummary, wallClockIso, RECIPE_WINDOW_FAIL_RATIO } from './recipeWindow.ts'

const row = (over: Record<string, unknown>) => ({
  timestamp: '2026-09-29T10:00:00Z', full_name: 'CLS/R1', align_fail: 'Pass', msr_check: 'Yes', fail_ratio: 1,
  ...over
}) as never

test('rows sort by distance from the clicked time, read as wall clock on both sides', () => {
  // Rows carry the KST wall clock with a Z tag; `at` is offset-less. Reading
  // the Z as UTC would put every row 9 h away.
  const rows = recipeWindowRows([
    row({ timestamp: '2026-09-29T10:25:00Z' }),
    row({ timestamp: '2026-09-29T09:55:00Z' }),
    row({ timestamp: '2026-09-29T10:10:00' })
  ], '2026-09-29T10:00:00')
  assert.deepEqual(rows.map(r => r.offsetMin), [-5, 10, 25])
})

test('flags align fail, a measurement without raw data, and a high failed-image share', () => {
  const [a, b, c, d] = recipeWindowRows([
    row({ align_fail: 'Fail' }),
    row({ msr_check: 'No' }),
    row({ fail_ratio: RECIPE_WINDOW_FAIL_RATIO }),
    row({ fail_ratio: RECIPE_WINDOW_FAIL_RATIO - 0.01 })
  ], '2026-09-29T10:00:00')
  assert.deepEqual([a!.flags, b!.flags, c!.flags, d!.flags], [['align'], ['msr'], ['images'], []])
})

test('summary counts measurements, distinct recipes and each failure kind', () => {
  const summary = recipeWindowSummary(recipeWindowRows([
    row({ full_name: 'CLS/R1', align_fail: 'Fail', fail_ratio: 40 }),
    row({ full_name: 'CLS/R1' }),
    row({ full_name: 'CLS/R2', msr_check: 'No' })
  ], '2026-09-29T10:00:00'))
  assert.deepEqual(summary, { total: 3, recipes: 2, align: 1, msr: 1, images: 1 })
})

test('an epoch from a time axis turns back into the offset-less wall clock it came from', () => {
  const epoch = new Date('2026-09-29T10:05:30').getTime()
  assert.equal(wallClockIso(epoch), '2026-09-29T10:05:30')
})

test('sorts on the exact distance, rounding only what it shows', () => {
  // Codex review: rounding first put a run 89 s away ahead of one 31 s away.
  const rows = recipeWindowRows([
    row({ timestamp: '2026-09-29T09:58:31Z' }),
    row({ timestamp: '2026-09-29T10:00:59Z' }),
    row({ timestamp: '2026-09-29T10:00:31Z' })
  ], '2026-09-29T10:00:00')
  assert.deepEqual(rows.map(r => r.row.timestamp), ['2026-09-29T10:00:31Z', '2026-09-29T10:00:59Z', '2026-09-29T09:58:31Z'])
})
