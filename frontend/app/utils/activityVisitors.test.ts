import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildVisitorsOption,
  visitorAxisLabel,
  visitorTooltip,
  visitorWindow
} from './activityVisitors.ts'

// 60 consecutive days ending 2026-10-02, visitors = position in the series.
const SIXTY = Array.from({ length: 60 }, (_, index) => {
  const day = new Date(Date.UTC(2026, 7, 4 + index))
  return { date: day.toISOString().slice(0, 10), visitors: index }
})

test('each window keeps the most recent days, today last', () => {
  assert.equal(SIXTY[59]!.date, '2026-10-02')

  const twoWeeks = visitorWindow(SIXTY, '2w')
  assert.equal(twoWeeks.length, 14)
  assert.equal(twoWeeks[0]!.date, '2026-09-19')
  assert.equal(twoWeeks[13]!.date, '2026-10-02')

  assert.equal(visitorWindow(SIXTY, '1m').length, 30)
  assert.equal(visitorWindow(SIXTY, '2m').length, 60)
})

test('a series shorter than the window is returned whole', () => {
  assert.deepEqual(visitorWindow(SIXTY.slice(-3), '2w'), SIXTY.slice(-3))
  assert.deepEqual(visitorWindow([], '2m'), [])
})

test('labels a day as MM.DD and names the weekday in the tooltip', () => {
  assert.equal(visitorAxisLabel('2026-10-02'), '10.02')
  // 2026-10-02 is a Friday, 2026-10-04 a Sunday.
  assert.equal(visitorTooltip('2026-10-02', 12), '2026-10-02 (금) · 방문자 12명')
  assert.equal(visitorTooltip('2026-10-04', 0), '2026-10-04 (일) · 방문자 0명')
})

test('draws one bar per day in order, on a whole-person axis', () => {
  const days = SIXTY.slice(-3)
  const option = buildVisitorsOption(days)

  const xAxis = option.xAxis as { data: string[] }
  assert.deepEqual(xAxis.data, ['2026-09-30', '2026-10-01', '2026-10-02'])
  const series = option.series as Array<{ type: string, data: number[] }>
  assert.equal(series[0]!.type, 'bar')
  assert.deepEqual(series[0]!.data, [57, 58, 59])
  // Half a visitor is not a thing: a quiet week must not tick 0, 0.5, 1.
  assert.equal((option.yAxis as { minInterval: number }).minInterval, 1)
})
