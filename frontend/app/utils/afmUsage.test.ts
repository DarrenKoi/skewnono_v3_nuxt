// Pure-logic tests for afmUsage. Run: node --test app/utils/afmUsage.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import {
  OTHER_RECIPES,
  dailyByRecipe,
  dayRows,
  failureDaily,
  hourGrid,
  hourOf,
  inWindow,
  latestDay,
  usageRows,
  usageSummary,
  usageWindow,
  usageDays
} from './afmUsage.ts'

let seq = 0
const row = (day: string | null, extra: Partial<AfmFileRow> = {}): AfmFileRow => ({
  filename: `f${String(++seq).padStart(4, '0')}`,
  recipe_name: 'R',
  lot_id: 'L',
  slot_number: '01',
  measured_info: '',
  formatted_date: day,
  time: '070000',
  point_count: 5,
  not_completed_count: 0,
  invalid_count: 0,
  ...extra
})

// What the office sends today: the failure columns null on every row.
const OFFICE = { not_completed_count: null, invalid_count: null }

test('an N-day window ends today, today included, and is exactly N days', () => {
  const rows = [row('2026-10-07'), row('2026-10-01'), row('2026-09-30'), row('2026-10-08')]
  const window = usageWindow(rows, 7, '2026-10-07')!
  assert.deepEqual(window, ['2026-10-01', '2026-10-07'])
  assert.equal(usageDays(window).length, 7)
  assert.deepEqual(inWindow(usageRows(rows), window).map(r => r.day), ['2026-10-07', '2026-10-01'])
  // A window crosses a month end on calendar days.
  assert.deepEqual(usageDays(usageWindow(rows, 30, '2026-10-07')!).slice(0, 2), ['2026-09-08', '2026-09-09'])
})

test('전체 spans the first to the last measured day; undated rows are in no window', () => {
  const rows = [row('2026-10-05'), row(null), row('2026-10-02'), row('')]
  const window = usageWindow(rows, null, '2026-10-07')!
  assert.deepEqual(window, ['2026-10-02', '2026-10-05'])
  const all = usageRows(rows)
  assert.equal(all.filter(r => r.day === null).length, 2)
  assert.equal(inWindow(all, window).length, 2)
  assert.equal(usageWindow([row(null)], null, '2026-10-07'), null)
})

test('idle days are filled with zero', () => {
  const days = usageDays(['2026-10-01', '2026-10-04'])
  const rows = usageRows([row('2026-10-01'), row('2026-10-04'), row('2026-10-04')])
  assert.deepEqual(days, ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'])
  assert.deepEqual(dailyByRecipe(rows, days), [{ name: 'R', values: [1, 0, 0, 2] }])
})

test('the stack is the five most-measured recipes + 기타, ties broken by name', () => {
  const day = '2026-10-01'
  const counts: Record<string, number> = { G: 1, B: 2, A: 2, F: 2, C: 3, D: 2, E: 2 }
  const made = Object.entries(counts).flatMap(([recipe_name, n]) =>
    Array.from({ length: n }, () => row(day, { recipe_name })))
  const stack = (rows: AfmFileRow[]) => dailyByRecipe(usageRows(rows), [day]).map(s => [s.name, s.values[0]])
  const expected = [['C', 3], ['A', 2], ['B', 2], ['D', 2], ['E', 2], [OTHER_RECIPES, 3]]
  assert.deepEqual(stack(made), expected)
  assert.deepEqual(stack([...made].reverse()), expected)
  // A measurement with no recipe name is never a recipe of its own.
  assert.deepEqual(stack([row(day, { recipe_name: '' }), row(day, { recipe_name: '' }), row(day)]), [['R', 1], [OTHER_RECIPES, 2]])
})

test('the hour is the head of a 4- or 6-digit code; null and NA have none', () => {
  assert.equal(hourOf('0705'), 7)
  assert.equal(hourOf('235959'), 23)
  assert.equal(hourOf('000000'), 0)
  for (const bad of [null, undefined, '', 'NA', '7', '2500', '07:05:00']) assert.equal(hourOf(bad), null)
  assert.equal(usageRows([row('2026-10-01', { time: '0705' })])[0]!.clock, '07:05:00')
})

test('the hour grid leaves out measurements with no time and counts them', () => {
  const days = ['2026-10-01', '2026-10-02']
  const grid = hourGrid(usageRows([
    row('2026-10-01', { time: '070000' }),
    row('2026-10-01', { time: '075959' }),
    row('2026-10-02', { time: '2300' }),
    row('2026-10-02', { time: null }),
    row('2026-10-02', { time: 'NA' })
  ]), days)
  assert.deepEqual(grid.cells.sort(), [[0, 7, 2], [1, 23, 1]])
  assert.equal(grid.max, 2)
  assert.equal(grid.missing, 2)
  assert.deepEqual(hourGrid([], days), { cells: [], max: 0, missing: 0 })
})

test('a null point_count stays out of the sum and is counted', () => {
  const summary = usageSummary(usageRows([
    row('2026-10-01', { point_count: 5 }),
    row('2026-10-01', { point_count: 0 }),
    row('2026-10-02', { point_count: null }),
    row('2026-10-02', { point_count: undefined, recipe_name: 'S', lot_id: '' })
  ]))
  assert.equal(summary.points, 5)
  assert.equal(summary.pointsMissing, 2)
  assert.equal(summary.count, 4)
  assert.equal(summary.activeDays, 2)
  assert.equal(summary.perActiveDay, 2)
  assert.equal(summary.recipes, 2)
  assert.equal(summary.lots, 1)
})

test('an empty window averages over nothing', () => {
  const summary = usageSummary([])
  assert.equal(summary.perActiveDay, null)
  assert.deepEqual(summary.notCompleted, { hit: 0, known: 0 })
})

test('all-null failure columns are "no data", not zeros', () => {
  const days = ['2026-10-01', '2026-10-02']
  const rows = usageRows([row('2026-10-01', OFFICE), row('2026-10-02', OFFICE)])
  assert.deepEqual(failureDaily(rows, days), { series: null, notCompletedMissing: 2, invalidMissing: 2 })
  assert.deepEqual(usageSummary(rows).notCompleted, { hit: 0, known: 0 })
})

test('a mixed set judges only the measurements that have the value', () => {
  const days = ['2026-10-01', '2026-10-02']
  const rows = usageRows([
    row('2026-10-01', { not_completed_count: 2, invalid_count: null }),
    row('2026-10-01', { not_completed_count: 0, invalid_count: 3 }),
    row('2026-10-02', OFFICE),
    row('2026-10-02', { not_completed_count: null, invalid_count: 0 }),
    // Outside the days drawn: neither a bar nor a missing count.
    row('2026-09-01', { not_completed_count: 9, invalid_count: 9 })
  ])
  assert.deepEqual(failureDaily(rows, days), {
    series: { notCompleted: [1, 0], invalid: [1, 0] },
    notCompletedMissing: 2,
    invalidMissing: 2
  })
  // b < total: two of the four in-window measurements carry not_completed_count.
  const summary = usageSummary(inWindow(rows, ['2026-10-01', '2026-10-02']))
  assert.deepEqual(summary.notCompleted, { hit: 1, known: 2 })
  assert.equal(summary.count, 4)
})

test('the selected day lists newest first, timeless measurements last', () => {
  const rows = usageRows([
    row('2026-10-01', { filename: 'b', time: '070000' }),
    row('2026-10-01', { filename: 'd', time: null }),
    row('2026-10-01', { filename: 'c', time: '0930' }),
    row('2026-10-01', { filename: 'a', time: '070000' }),
    row('2026-10-03', { filename: 'z' }),
    row(null, { filename: 'n' })
  ])
  assert.deepEqual(dayRows(rows, '2026-10-01').map(r => r.row.filename), ['c', 'a', 'b', 'd'])
  assert.equal(latestDay(rows), '2026-10-03')
  assert.equal(latestDay(usageRows([row(null)])), null)
})
