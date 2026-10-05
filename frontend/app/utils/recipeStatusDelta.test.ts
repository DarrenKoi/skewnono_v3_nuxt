// Run: node --test app/utils/recipeStatusDelta.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { RecipeTatSummary } from '~/composables/useRecipeTatApi'
import type { FailIssueSummary } from '~/composables/useFailIssueApi'
import {
  NO_PREVIOUS_PERIOD,
  failDeltaItems,
  isAnchorIncluded,
  previousWindow,
  tatDeltaItems
} from './recipeStatusDelta.ts'

const fmt = (seconds: number) => `${seconds}s`

const tat = (over: Partial<RecipeTatSummary> = {}): RecipeTatSummary => ({
  tool_type: 'CD-SEM' as RecipeTatSummary['tool_type'],
  fab_names: ['R3'],
  start_date: '2026-09-22',
  end_date: '2026-10-05',
  anchor_date: '2026-10-05',
  total_tat_seconds: 1000,
  total_recipes: 50,
  total_executions: 1328,
  avg_meastime: 40,
  ...over
})

const fail = (over: Partial<FailIssueSummary> = {}): FailIssueSummary => ({
  tool_type: 'CD-SEM' as FailIssueSummary['tool_type'],
  fab_names: ['R3'],
  start_date: '2026-09-22',
  end_date: '2026-10-05',
  anchor_date: '2026-10-05',
  total_executions: 1328,
  align_fail_count: 30,
  align_fail_rate: 0.03,
  align_na_count: 0,
  meas_fail_count: 60,
  meas_fail_rate: 0.05,
  meas_fail_threshold: 15,
  distinct_equipment: 10,
  distinct_recipes: 50,
  distinct_lots: 20,
  ...over
})

const prevTat = (over: Partial<RecipeTatSummary> = {}) =>
  tat({ start_date: '2026-09-08', end_date: '2026-09-21', total_executions: 1204, ...over })
const prevFail = (over: Partial<FailIssueSummary> = {}) =>
  fail({ start_date: '2026-09-08', end_date: '2026-09-21', total_executions: 1204, ...over })

const byKey = <T extends { key: string }>(items: T[], key: string): T => {
  const found = items.find(item => item.key === key)
  assert.ok(found, `missing ${key}`)
  return found
}

test('previousWindow returns the same-length window immediately before', () => {
  assert.deepEqual(previousWindow('2026-09-22', '2026-09-28'), { start: '2026-09-15', end: '2026-09-21' })
})

test('previousWindow crosses a month end', () => {
  assert.deepEqual(previousWindow('2026-10-01', '2026-10-14'), { start: '2026-09-17', end: '2026-09-30' })
})

test('previousWindow of a 1-day window is the day before', () => {
  assert.deepEqual(previousWindow('2026-03-01', '2026-03-01'), { start: '2026-02-28', end: '2026-02-28' })
})

test('previousWindow lands on Feb 29 in a leap year', () => {
  assert.deepEqual(previousWindow('2028-03-01', '2028-03-01'), { start: '2028-02-29', end: '2028-02-29' })
  assert.deepEqual(previousWindow('2028-03-01', '2028-03-07'), { start: '2028-02-23', end: '2028-02-29' })
})

test('isAnchorIncluded is true when the window ends on or after the anchor', () => {
  assert.equal(isAnchorIncluded('2026-10-05', '2026-10-05'), true)
  assert.equal(isAnchorIncluded('2026-10-06', '2026-10-05'), true)
  assert.equal(isAnchorIncluded('2026-10-04', '2026-10-05'), false)
  assert.equal(isAnchorIncluded('2026-10-05', '2026-10-05T08:00:00'), true)
  assert.equal(isAnchorIncluded('', '2026-10-05'), false)
  assert.equal(isAnchorIncluded('2026-10-05', ''), false)
})

test('a missing previous summary yields 이전 기간 없음 on every KPI', () => {
  for (const item of tatDeltaItems(tat(), undefined, fmt)) {
    assert.deepEqual(
      { delta: item.delta, tone: item.tone, title: item.title },
      { delta: NO_PREVIOUS_PERIOD, tone: 'none', title: '' }
    )
  }
  assert.equal(failDeltaItems(fail(), null, 'align').length, 3)
})

test('zero previous executions yields 이전 기간 없음 with both denominators in the title', () => {
  const items = failDeltaItems(fail(), prevFail({ total_executions: 0 }), 'meas')
  for (const item of items) {
    assert.equal(item.delta, '이전 기간 없음')
    assert.equal(item.tone, 'none')
    assert.equal(item.title, '이전 14일(09-08~09-21) 0건 · 현재 1,328건')
  }
})

test('title carries the previous window and both denominators', () => {
  const [first] = tatDeltaItems(tat(), prevTat(), fmt)
  assert.equal(first?.title, '이전 14일(09-08~09-21) 1,204건 대비 · 현재 1,328건')
})

test('executions and recipes stay neutral whichever way they move', () => {
  const up = tatDeltaItems(tat(), prevTat({ total_recipes: 40 }), fmt)
  assert.deepEqual(
    [byKey(up, 'totalExecutions').delta, byKey(up, 'totalExecutions').tone],
    ['+124 (+10.3%)', 'neutral']
  )
  assert.deepEqual(
    [byKey(up, 'distinctRecipes').delta, byKey(up, 'distinctRecipes').tone],
    ['+10 (+25.0%)', 'neutral']
  )
  const down = tatDeltaItems(tat({ total_executions: 1000 }), prevTat(), fmt)
  assert.deepEqual(
    [byKey(down, 'totalExecutions').delta, byKey(down, 'totalExecutions').tone],
    ['−204 (−16.9%)', 'neutral']
  )
})

test('total TAT and avg meastime: lower is ok, higher is bad, equal is neutral', () => {
  const lower = tatDeltaItems(tat(), prevTat({ total_tat_seconds: 1250, avg_meastime: 50 }), fmt)
  assert.deepEqual(
    [byKey(lower, 'totalTat').delta, byKey(lower, 'totalTat').tone],
    ['−250s (−20.0%)', 'ok']
  )
  assert.deepEqual(
    [byKey(lower, 'avgMeastime').delta, byKey(lower, 'avgMeastime').tone],
    ['−10s (−20.0%)', 'ok']
  )
  const higher = tatDeltaItems(tat(), prevTat({ total_tat_seconds: 800, avg_meastime: 32 }), fmt)
  assert.deepEqual(
    [byKey(higher, 'totalTat').delta, byKey(higher, 'totalTat').tone],
    ['+200s (+25.0%)', 'bad']
  )
  assert.equal(byKey(higher, 'avgMeastime').tone, 'bad')
  const same = tatDeltaItems(tat(), prevTat(), fmt)
  assert.deepEqual(
    [byKey(same, 'totalTat').delta, byKey(same, 'totalTat').tone],
    ['0s (0.0%)', 'neutral']
  )
})

test('fail rate is reported in %p with one decimal; lower is ok', () => {
  const up = failDeltaItems(fail({ align_fail_rate: 0.034 }), prevFail(), 'align')
  assert.deepEqual(
    [byKey(up, 'failRatio').delta, byKey(up, 'failRatio').tone],
    ['+0.4%p', 'bad']
  )
  const down = failDeltaItems(fail({ meas_fail_rate: 0.0375 }), prevFail(), 'meas')
  assert.deepEqual(
    [byKey(down, 'failRatio').delta, byKey(down, 'failRatio').tone],
    ['−1.3%p', 'ok']
  )
})

test('%p rounding: a change below 0.05%p reads 0.0%p and takes no colour', () => {
  const tiny = failDeltaItems(fail({ align_fail_rate: 0.0304 }), prevFail(), 'align')
  assert.deepEqual(
    [byKey(tiny, 'failRatio').delta, byKey(tiny, 'failRatio').tone],
    ['0.0%p', 'neutral']
  )
})

test('failDeltaItems reads the section it is given; fail count stays neutral', () => {
  const prev = prevFail({ align_fail_count: 20, meas_fail_count: 80 })
  assert.deepEqual(
    [byKey(failDeltaItems(fail(), prev, 'align'), 'failCount').delta,
      byKey(failDeltaItems(fail(), prev, 'align'), 'failCount').tone],
    ['+10 (+50.0%)', 'neutral']
  )
  assert.equal(byKey(failDeltaItems(fail(), prev, 'meas'), 'failCount').delta, '−20 (−25.0%)')
})

test('a zero previous value drops the percent instead of dividing by zero', () => {
  const items = failDeltaItems(fail(), prevFail({ align_fail_count: 0 }), 'align')
  assert.equal(byKey(items, 'failCount').delta, '+30')
})
