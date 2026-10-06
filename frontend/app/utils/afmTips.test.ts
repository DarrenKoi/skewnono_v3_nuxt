// Pure-logic tests for afmTips. Run: node --test app/utils/afmTips.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { mountedTip, tipCategories, tipPoints, tipRecipes, widthIsPerTip } from './afmTips.ts'

const row = (n: number, extra: Partial<AfmFileRow> = {}): AfmFileRow => ({
  filename: `f${n}`,
  recipe_name: 'R',
  lot_id: 'L',
  slot_number: '01',
  measured_info: '',
  formatted_date: `2026-10-${String(n).padStart(2, '0')}`,
  time: '070000',
  tip_id: 'DT-NCHR_CM',
  tip_cassette_id: 'TC10',
  tip_port_no: '1',
  tip_slot_no: '3',
  tip_width: 40,
  approach_count_mean: 1,
  mileage_mean: 10,
  not_completed_count: 0,
  invalid_count: 0,
  ...extra
})

test('tipPoints keeps the measurements that name a tip, in time order', () => {
  const points = tipPoints([
    row(2, { tip_slot_no: null }),
    row(1),
    row(3, { tip_id: null }),
    row(4, { tip_id: undefined })
  ])
  assert.deepEqual(points.map(p => [p.key, p.type, p.tip]), [
    ['f1', 'DT-NCHR_CM', 'DT-NCHR_CM · TC10/1/3'],
    ['f2', 'DT-NCHR_CM', 'DT-NCHR_CM · TC10/1/?']
  ])
  assert.equal(points[0]!.time, Date.parse('2026-10-01 07:00:00'))
})

test('tipCategories judges a tip against its own type, whatever slot it sits in', () => {
  const widths = [40, 41, 39, 40, 41, 39, 40, 60]
  const [cdr, fixed] = tipCategories(tipPoints([
    ...widths.map((tip_width, i) => row(i + 1, { tip_width, tip_slot_no: i < 4 ? '3' : '9' })),
    // Not recorded: out of the statistics, never an outlier.
    row(9, { tip_width: null, not_completed_count: null, tip_slot_no: '9' }),
    // Another type with a width that would be far out among the others.
    row(10, { tip_id: 'CDR-70', tip_width: 70 })
  ]))
  assert.deepEqual([cdr!.type, fixed!.type], ['CDR-70', 'DT-NCHR_CM'])

  const width = fixed!.stats.find(s => s.param === 'tipWidth')!
  assert.deepEqual([width.n, width.outliers], [8, 1])
  assert.equal(fixed!.stats.find(s => s.param === 'notCompleted')!.n, 8)
  assert.deepEqual(fixed!.flags.map(f => [f.point.key, f.params]), [['f8', ['tipWidth']]])
  // Newest tip first; the flag is counted on the tip that measured it.
  // Worst tip first; one of its last five outside is 주의, none is 정상.
  assert.deepEqual(fixed!.tips.map(t => [t.tip, t.points.length, t.flagged, t.recentOut, t.state]), [
    ['DT-NCHR_CM · TC10/1/9', 5, 1, 1, 'warn'],
    ['DT-NCHR_CM · TC10/1/3', 4, 0, 0, 'ok']
  ])
  assert.deepEqual(fixed!.tips[0]!.recentParams, ['tipWidth'])

  // Too few measurements to call anything an outlier.
  assert.deepEqual(cdr!.stats.map(s => s.limits), [null, null, null, null, null])
  // Mileage is a counter, not a level: no limits however many values there are.
  assert.deepEqual([fixed!.stats.find(s => s.param === 'mileage')!.n, fixed!.stats.find(s => s.param === 'mileage')!.limits], [9, null])
  assert.deepEqual(cdr!.flags, [])
  assert.equal(cdr!.tips[0]!.state, 'hold')
})

test('a tip is judged on its last five measurements only', () => {
  const widths = [60, 40, 41, 39, 40, 41, 39, 40, 41, 39, 61, 40, 62]
  const points = tipPoints(widths.map((tip_width, i) => row(i + 1, {
    tip_width,
    tip_slot_no: i < 6 ? '3' : '9',
    recipe_name: i % 3 ? 'A' : 'B'
  })))
  const [fixed] = tipCategories(points)
  // The newer tip went out twice in its last five; the older one's excursion
  // is six measurements back, so it no longer speaks for the tip.
  assert.deepEqual(fixed!.tips.map(t => [t.tip, t.flagged, t.recentOut, t.state]), [
    ['DT-NCHR_CM · TC10/1/9', 2, 2, 'bad'],
    ['DT-NCHR_CM · TC10/1/3', 1, 0, 'ok']
  ])
  assert.deepEqual(fixed!.tips[0]!.recipes, [{ recipe: 'A', count: 4 }, { recipe: 'B', count: 3 }])
  assert.equal(mountedTip(points), 'DT-NCHR_CM · TC10/1/9')
  assert.equal(mountedTip([]), null)
  assert.deepEqual(tipRecipes(points), [{ recipe: 'A', count: 8 }, { recipe: 'B', count: 5 }])
})

test('an MCNT tip width is held against that tip, not its type', () => {
  assert.deepEqual(['MCNT-150', 'mcnt_500', 'DT-NCHR_CM'].map(widthIsPerTip), [true, true, false])
  // Two slots at their own levels: a type-wide band would straddle both and
  // miss the reading that left its own slot's.
  const low = [34, 34.2, 33.9, 34.1, 34, 36]
  const high = [39, 38.8, 39.1, 38.9, 39]
  const [mcnt] = tipCategories(tipPoints([
    ...low.map((tip_width, i) => row(i + 1, { tip_id: 'MCNT-150', tip_width, mileage_mean: 5000 * i })),
    ...high.map((tip_width, i) => row(i + 10, { tip_id: 'MCNT-150', tip_width, tip_slot_no: '9' }))
  ]))
  assert.equal(mcnt!.stats.find(s => s.param === 'tipWidth')!.limits, null)
  assert.deepEqual(mcnt!.flags.map(f => [f.point.key, f.params]), [['f6', ['tipWidth']]])
  const [warned, fine] = mcnt!.tips
  assert.deepEqual([warned!.tip, warned!.state, fine!.state], ['MCNT-150 · TC10/1/3', 'warn', 'ok'])
  assert.ok(warned!.widthLimits!.ucl < 36 && fine!.widthLimits!.lcl > 36)
})
