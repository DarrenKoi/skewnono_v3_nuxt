// Pure-logic tests for afmRecipes. Run: node --test app/utils/afmRecipes.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import {
  dailyCounts,
  daysAgoLabel,
  failedLabel,
  fileLabel,
  filterRecipes,
  pointLabel,
  recipeBoard,
  sortRecipes,
  tileCounts,
  tipUsage,
  type RecipeSummary
} from './afmRecipes.ts'

const TODAY = '2026-10-07'

let seq = 0
const row = (recipe: string, day: string | null, extra: Partial<AfmFileRow> = {}): AfmFileRow => ({
  filename: `f${++seq}`,
  recipe_name: recipe,
  lot_id: 'L1',
  slot_number: '01',
  measured_info: '',
  formatted_date: day,
  time: '070000',
  ...extra
})

// The office today: every summary column null on every row.
const OFFICE_NULLS: Partial<AfmFileRow> = {
  time: null,
  point_count: null,
  tip_id: null,
  tip_cassette_id: null,
  tip_port_no: null,
  tip_slot_no: null,
  tip_width: null,
  approach_count_mean: null,
  mileage_mean: null,
  not_completed_count: null,
  invalid_count: null
}

const one = (rows: AfmFileRow[], name = 'A'): RecipeSummary =>
  recipeBoard(rows, TODAY).recipes.find(r => r.recipe === name)!

test('groups by recipe, leaving out and counting the rows with no recipe name', () => {
  const board = recipeBoard([
    row('A', '2026-10-07'),
    row('B', '2026-10-06'),
    row('', '2026-10-07'),
    row('  ', '2026-10-07'),
    row('A', null),
    row(null as unknown as string, '2026-10-07')
  ], TODAY)
  assert.deepEqual(board.recipes.map(r => [r.recipe, r.count]), [['A', 2], ['B', 1]])
  assert.equal(board.measured, 3)
  assert.equal(board.unnamed, 3)
  assert.equal(board.undated, 1)
})

test('first / last read only the dated rows; all-null dates leave them null', () => {
  const some = one([row('A', '2026-10-03'), row('A', null), row('A', '2026-09-20'), row('A', '2026-10-05')])
  assert.deepEqual([some.first, some.last, some.daysAgo, some.dated], ['2026-09-20', '2026-10-05', 2, 3])
  // Newest first, the undated row last.
  assert.deepEqual(some.rows.map(r => r.formatted_date), ['2026-10-05', '2026-10-03', '2026-09-20', null])

  const none = one([row('A', null, OFFICE_NULLS), row('A', null, OFFICE_NULLS)])
  assert.deepEqual([none.first, none.last, none.daysAgo, none.dated], [null, null, null, 0])
  assert.deepEqual(none.spark, Array.from({ length: 14 }, () => 0))
  assert.deepEqual(dailyCounts(none), [])
  assert.equal(daysAgoLabel(none.daysAgo), '')
})

test('rows of one day order by the time code, without it last of that day', () => {
  const r = one([
    row('A', '2026-10-05', { time: '070000', filename: 'early' }),
    row('A', '2026-10-05', { time: '153000', filename: 'late' }),
    row('A', '2026-10-05', { time: null, filename: 'untimed' })
  ])
  assert.deepEqual(r.rows.map(x => x.filename), ['late', 'early', 'untimed'])
})

test('days-ago at 0 / 7 / 30 / 31 decides the recent and stale tiles', () => {
  const board = recipeBoard([
    row('D0', '2026-10-07'),
    row('D6', '2026-10-01'),
    row('D7', '2026-09-30'),
    row('D30', '2026-09-07'),
    row('D31', '2026-09-06'),
    row('NODATE', null)
  ], TODAY)
  const ago = Object.fromEntries(board.recipes.map(r => [r.recipe, r.daysAgo]))
  assert.deepEqual(ago, { D0: 0, D6: 6, D7: 7, D30: 30, D31: 31, NODATE: null })
  assert.deepEqual([0, 7, 31].map(daysAgoLabel), ['오늘', '7일 전', '31일 전'])

  const names = (tile: 'recent' | 'stale' | 'once') => filterRecipes(board.recipes, '', tile).map(r => r.recipe)
  assert.deepEqual(names('recent'), ['D0', 'D6'])
  assert.deepEqual(names('stale'), ['D31'])
  // Every recipe here has one measurement — the undated one too.
  assert.equal(names('once').length, 6)
  assert.deepEqual(tileCounts(board.recipes), { recent: 2, stale: 1, once: 6 })
})

test('1회만 측정 counts measurements, not days', () => {
  const board = recipeBoard([row('A', '2026-10-07'), row('A', '2026-10-07'), row('B', '2026-10-07')], TODAY)
  assert.deepEqual(filterRecipes(board.recipes, '', 'once').map(r => r.recipe), ['B'])
})

test('point range: single, range, none — nulls are in neither end', () => {
  assert.equal(pointLabel(one([row('A', TODAY, { point_count: 5 }), row('A', TODAY, { point_count: 5 })])), '5')
  assert.equal(pointLabel(one([row('A', TODAY, { point_count: 36 }), row('A', TODAY, { point_count: null }), row('A', TODAY, { point_count: 5 })])), '5–36')
  assert.equal(pointLabel(one([row('A', TODAY, { point_count: null }), row('A', TODAY)])), '–')
})

test('distinct lots ignore empty lot ids', () => {
  assert.equal(one([row('A', TODAY, { lot_id: 'X' }), row('A', TODAY, { lot_id: '' }), row('A', TODAY, { lot_id: 'X' }), row('A', TODAY, { lot_id: 'Y' })]).lots, 2)
})

test('file kinds: only the ones present, in order, with a fraction when partial', () => {
  const r = one([
    row('A', TODAY, { has_data: true, has_profile: true, has_tip: true }),
    row('A', TODAY, { has_data: true, has_profile: false, has_tip: true }),
    row('A', TODAY, { has_data: true, has_tip: false })
  ])
  assert.deepEqual(r.files.map(f => fileLabel(f, r.count)), ['Data', 'Profile 1/3', 'Tip 2/3'])
})

test('14-day sparkline: today is the last bar, day −14 is outside', () => {
  const r = one([
    row('A', '2026-10-07'),
    row('A', '2026-10-07'),
    row('A', '2026-09-24'), // day −13: the first bar
    row('A', '2026-09-23'), // day −14: out
    row('A', '2026-10-08'), // tomorrow: out
    row('A', null)
  ])
  assert.equal(r.spark.length, 14)
  assert.equal(r.spark[0], 1)
  assert.equal(r.spark[13], 2)
  assert.equal(r.spark.reduce((a, b) => a + b, 0), 3)
})

test('미완료: a / b over the rows that recorded the value; – when none did', () => {
  const some = one([
    row('A', TODAY, { not_completed_count: 3 }),
    row('A', TODAY, { not_completed_count: 0 }),
    row('A', TODAY, { not_completed_count: null }),
    row('A', TODAY)
  ])
  assert.deepEqual([some.failed, some.failedOf, failedLabel(some)], [1, 2, '1 / 2'])
  const none = one([row('A', TODAY, OFFICE_NULLS), row('A', TODAY, OFFICE_NULLS)])
  assert.deepEqual([none.failed, none.failedOf, failedLabel(none)], [null, 0, '–'])
})

test('sort puts nulls last in both directions and breaks ties by name', () => {
  const board = recipeBoard([
    row('B', '2026-10-01', { point_count: 9, not_completed_count: 1 }),
    row('A', '2026-10-05', { point_count: 5, not_completed_count: 0 }),
    row('N', null, OFFICE_NULLS),
    row('C', '2026-10-05', { point_count: 5 }),
    row('C', '2026-10-05', { point_count: 36 })
  ], TODAY)
  const order = (key: Parameters<typeof sortRecipes>[1]['key'], desc: boolean) =>
    sortRecipes(board.recipes, { key, desc }).map(r => r.recipe).join('')
  assert.equal(order('last', true), 'ACBN')
  assert.equal(order('last', false), 'BACN')
  assert.equal(order('first', false), 'BACN')
  assert.equal(order('point', false), 'ACBN')
  assert.equal(order('point', true), 'BCAN')
  // C and N recorded no 미완료 value.
  assert.equal(order('failed', true), 'BACN')
  assert.equal(order('failed', false), 'ABCN')
  assert.equal(order('count', true), 'CABN')
  assert.equal(order('recipe', true), 'NCBA')
  assert.equal(order('lots', true), 'ABCN')
})

test('name filter: every term, any case, any order; combines with a tile', () => {
  const board = recipeBoard([
    row('CMP_POST_36PT', '2026-10-07'),
    row('CMP_PRE', '2026-08-01'),
    row('Fi-Tapping TEST', '2026-10-07')
  ], TODAY)
  const names = (q: string, tile: 'recent' | 'stale' | 'once' | null = null) =>
    filterRecipes(board.recipes, q, tile).map(r => r.recipe)
  assert.deepEqual(names('cmp'), ['CMP_POST_36PT', 'CMP_PRE'])
  assert.deepEqual(names('  36pt   CMP '), ['CMP_POST_36PT'])
  assert.deepEqual(names('test fi'), ['Fi-Tapping TEST'])
  assert.deepEqual(names('cmp x'), [])
  assert.equal(names('').length, 3)
  assert.deepEqual(names('cmp', 'stale'), ['CMP_PRE'])
})

test('daily counts span first to last with the empty days in', () => {
  const r = one([row('A', '2026-09-29'), row('A', '2026-10-02'), row('A', '2026-10-02'), row('A', null)])
  assert.deepEqual(dailyCounts(r), [
    { day: '2026-09-29', count: 1 },
    { day: '2026-09-30', count: 0 },
    { day: '2026-10-01', count: 0 },
    { day: '2026-10-02', count: 2 }
  ])
})

test('tip usage: most used first, rows naming no tip in no count', () => {
  const r = one([
    row('A', TODAY, { tip_id: 'MCNT-150' }),
    row('A', TODAY, { tip_id: 'MCNT-500' }),
    row('A', TODAY, { tip_id: 'MCNT-500' }),
    row('A', TODAY, { tip_id: null }),
    row('A', TODAY)
  ])
  assert.deepEqual(tipUsage(r), [{ tip: 'MCNT-500', count: 2 }, { tip: 'MCNT-150', count: 1 }])
  assert.deepEqual(tipUsage(one([row('A', TODAY, OFFICE_NULLS)])), [])
})
