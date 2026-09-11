import assert from 'node:assert/strict'
import test from 'node:test'
import { calendarWeeks } from './activityCalendar.ts'

test('calendar aligns Monday rows across leap day and month boundaries without inventing visits', () => {
  const days = [
    { date: '2024-02-29', count: 2 },
    { date: '2024-03-01', count: 0 },
    { date: '2024-03-03', count: 4 },
    { date: '2024-03-04', count: 1 }
  ]
  const weeks = calendarWeeks(days)
  assert.equal(weeks.length, 2)
  assert.equal(weeks[0]!.start, '2024-02-26')
  assert.equal(weeks[0]!.month, '3월')
  assert.equal(weeks[0]!.days[3], days[0])
  assert.equal(weeks[0]!.days[5], null)
  assert.equal(weeks[0]!.days[6], days[2])
  assert.equal(weeks[1]!.days[0], days[3])
  assert.deepEqual(calendarWeeks([]), [])
})
