// Pure-logic tests for afmTips. Run: node --test app/utils/afmTips.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import { tipCategories, tipPoints } from './afmTips.ts'

const row = (n: number, extra: Partial<AfmFileRow> = {}): AfmFileRow => ({
  filename: `f${n}`,
  recipe_name: 'R',
  lot_id: 'L',
  slot_number: '01',
  measured_info: '',
  formatted_date: `2026-10-${String(n).padStart(2, '0')}`,
  time: '070000',
  tip_id: 'MCNT-150',
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
    ['f1', 'MCNT-150', 'MCNT-150 · TC10/1/3'],
    ['f2', 'MCNT-150', 'MCNT-150 · TC10/1/?']
  ])
  assert.equal(points[0]!.time, Date.parse('2026-10-01 07:00:00'))
})

test('tipCategories judges a tip against its own type, whatever slot it sits in', () => {
  const widths = [40, 41, 39, 40, 41, 39, 40, 60]
  const [cdr, mcnt] = tipCategories(tipPoints([
    ...widths.map((tip_width, i) => row(i + 1, { tip_width, tip_slot_no: i < 4 ? '3' : '9' })),
    // Not recorded: out of the statistics, never an outlier.
    row(9, { tip_width: null, not_completed_count: null, tip_slot_no: '9' }),
    // Another type with a width that would be far out among the MCNT ones.
    row(10, { tip_id: 'CDR-70', tip_width: 70 })
  ]))
  assert.deepEqual([cdr!.type, mcnt!.type], ['CDR-70', 'MCNT-150'])

  const width = mcnt!.stats.find(s => s.param === 'tipWidth')!
  assert.deepEqual([width.n, width.outliers], [8, 1])
  assert.equal(mcnt!.stats.find(s => s.param === 'notCompleted')!.n, 8)
  assert.deepEqual(mcnt!.flags.map(f => [f.point.key, f.params]), [['f8', ['tipWidth']]])
  // Newest tip first; the flag is counted on the tip that measured it.
  assert.deepEqual(mcnt!.tips.map(t => [t.tip, t.count, t.flagged]), [
    ['MCNT-150 · TC10/1/9', 5, 1],
    ['MCNT-150 · TC10/1/3', 4, 0]
  ])

  // Too few measurements to call anything an outlier.
  assert.deepEqual(cdr!.stats.map(s => s.limits), [null, null, null, null, null])
  assert.deepEqual(cdr!.flags, [])
})
