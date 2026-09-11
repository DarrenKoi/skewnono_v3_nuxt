import assert from 'node:assert/strict'
import test from 'node:test'
import { buildCalendarOption, visitLabel } from './activityCalendar.ts'

const colors = { empty: '#eee', full: '#c00', ink: '#000', muted: '#888' }

test('calendar option spans the series, maps each day to a heatmap cell and scales to the busiest day', () => {
  const option = buildCalendarOption([
    { date: '2026-06-15', count: 0 },
    { date: '2026-06-16', count: 4 },
    { date: '2026-06-17', count: 1 }
  ], colors)
  const calendar = option.calendar as { range: string[], dayLabel: { firstDay: number } }
  assert.deepEqual(calendar.range, ['2026-06-15', '2026-06-17'])
  assert.equal(calendar.dayLabel.firstDay, 1)
  const [heatmap] = option.series as { data: unknown[] }[]
  assert.deepEqual(heatmap!.data, [['2026-06-15', 0], ['2026-06-16', 4], ['2026-06-17', 1]])
  assert.equal((option.visualMap as { max: number }).max, 4)
})

test('an all-zero series still has a non-zero scale and an empty one has no range', () => {
  assert.equal((buildCalendarOption([{ date: '2026-06-15', count: 0 }], colors).visualMap as { max: number }).max, 1)
  assert.equal((buildCalendarOption([], colors).calendar as { range?: unknown }).range, undefined)
})

test('visitLabel names the day and its page opens', () => {
  assert.equal(visitLabel({ date: '2026-06-16', count: 1234 }), '2026-06-16 · 페이지 조회 1,234회')
})
