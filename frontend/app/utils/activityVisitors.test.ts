import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildVisitorsOption,
  frequentVisitors,
  stickinessPercent,
  visitFrequencyBuckets,
  visitorAxisLabel,
  visitorTooltip,
  visitorWindow,
  visitorsByTeam
} from './activityVisitors.ts'

// 60 consecutive days ending 2026-10-02, visitors = position in the series.
const SIXTY = Array.from({ length: 60 }, (_, index) => {
  const day = new Date(Date.UTC(2026, 7, 4 + index))
  return { date: day.toISOString().slice(0, 10), visitors: index, wau: index + 10, mau: index + 100 }
})

const user = (
  user_id: string,
  days_active_30d: number,
  dept_nm: string | null = null,
  emp_nm: string | null = null,
  requests_30d = 10
) => ({ user_id, days_active_30d, dept_nm, emp_nm, requests_30d })

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

test('labels a day as MM.DD and names the weekday and all three counts in the tooltip', () => {
  assert.equal(visitorAxisLabel('2026-10-02'), '10.02')
  // 2026-10-02 is a Friday.
  assert.equal(
    visitorTooltip({ date: '2026-10-02', visitors: 12, wau: 30, mau: 1080 }),
    '2026-10-02 (금)<br>DAU 12명 · WAU 30명 · MAU 1,080명'
  )
})

test('draws one metric at a time: DAU as bars from zero, WAU and MAU as fitted lines', () => {
  const days = SIXTY.slice(-3)
  type Drawn = { xAxis: { data: string[] }, yAxis: { min?: number, scale?: boolean, minInterval: number }, series: Array<{ name: string, type: string, data: number[] }> }
  const draw = (metric?: 'dau' | 'wau' | 'mau') => buildVisitorsOption(days, metric) as Drawn

  assert.deepEqual(draw().xAxis.data, ['2026-09-30', '2026-10-01', '2026-10-02'])
  assert.deepEqual(draw().series.map(s => [s.name, s.type, s.data]), [['DAU', 'bar', [57, 58, 59]]])
  assert.deepEqual(draw('wau').series.map(s => [s.name, s.type, s.data]), [['WAU', 'line', [67, 68, 69]]])
  assert.deepEqual(draw('mau').series.map(s => [s.name, s.type, s.data]), [['MAU', 'line', [157, 158, 159]]])

  // A bar's length is its value; a rolling count's movement is what is read.
  assert.equal(draw('dau').yAxis.min, 0)
  assert.equal(draw('mau').yAxis.min, undefined)
  assert.equal(draw('mau').yAxis.scale, true)
  // Half a visitor is not a thing: a quiet week must not tick 0, 0.5, 1.
  assert.equal(draw('wau').yAxis.minInterval, 1)
})

test('stickiness is DAU over MAU, and absent when nobody came all month', () => {
  assert.equal(stickinessPercent({ visitors: 5, mau: 9 }), 56)
  assert.equal(stickinessPercent({ visitors: 0, mau: 9 }), 0)
  assert.equal(stickinessPercent({ visitors: 0, mau: 0 }), null)
  assert.equal(stickinessPercent(undefined), null)
})

test('ranks people by active days, requests then employee number breaking ties', () => {
  const rows = frequentVisitors([
    user('100', 3, 'A팀', '김하나'),
    user('200', 20, 'B팀', null),
    user('300', 20, null, '이두리', 99),
    user('400', 1)
  ])

  // Every person, ranked — the list component is what shows the first ten.
  assert.deepEqual(rows, [
    { label: '이두리', hint: '—', count: 20 },
    // No directory name: the employee number stands in, as in the table.
    { label: '200', hint: 'B팀', count: 20 },
    { label: '김하나', hint: 'A팀', count: 3 },
    { label: '400', hint: '—', count: 1 }
  ])
})

test('buckets people by how many of the last 30 days they came', () => {
  const buckets = visitFrequencyBuckets(
    [1, 1, 2, 5, 6, 15, 16, 30].map((days, index) => user(String(index), days))
  )

  assert.deepEqual(buckets, [
    { label: '1일', hint: '한 번 들른 사용자', count: 2 },
    { label: '2–5일', hint: '가끔', count: 2 },
    { label: '6–15일', hint: '주 2–3회', count: 2 },
    { label: '16일 이상', hint: '거의 매일', count: 2 }
  ])
  // Every bucket is listed even when empty — a missing row reads as a bug.
  assert.deepEqual(visitFrequencyBuckets([]).map(b => b.count), [0, 0, 0, 0])
})

test('counts people per team, largest first, with the unknown team named', () => {
  assert.deepEqual(
    visitorsByTeam([
      user('1', 3, 'B팀'),
      user('2', 3, 'A팀'),
      user('3', 3, 'B팀'),
      user('4', 3, null),
      user('5', 3, '  ')
    ]),
    [
      { label: 'B팀', count: 2 },
      { label: '소속 미확인', count: 2 },
      { label: 'A팀', count: 1 }
    ]
  )
})
