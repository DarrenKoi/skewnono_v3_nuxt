import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildRequestsOption,
  requestKpis,
  requestRemainderNote,
  requestTooltip,
  requestsPerPersonDay,
  topRequesters
} from './activityRequests.ts'

// 40 days ending 2026-10-02: requests = 10 × position, two people every day.
const FORTY = Array.from({ length: 40 }, (_, index) => {
  const day = new Date(Date.UTC(2026, 7, 24 + index))
  return { date: day.toISOString().slice(0, 10), requests: index * 10, users: 2 }
})

test('the KPI cards sum today, the last 7 and the last 30 days of one series', () => {
  assert.equal(FORTY[39]!.date, '2026-10-02')
  const [today, week, month, perPersonDay] = requestKpis(FORTY)

  assert.equal(today!.value, '390')
  // positions 33..39 → (33+…+39) × 10
  assert.equal(week!.value, '2,520')
  // positions 10..39 → (10+…+39) × 10
  assert.equal(month!.value, '7,350')
  // 7,350 requests over 30 days × 2 people
  assert.equal(perPersonDay!.value, '122.5')
})

test('requests per person-day is no answer when nobody came', () => {
  assert.equal(requestsPerPersonDay([{ date: '2026-10-02', requests: 0, users: 0 }]), null)
  assert.equal(requestKpis([{ date: '2026-10-02', requests: 0, users: 0 }])[3]!.value, '—')
  assert.equal(requestKpis([])[0]!.value, '0')
})

test('the tooltip names the weekday, requests and requesters', () => {
  assert.equal(
    requestTooltip({ date: '2026-10-02', requests: 1234, users: 5 }),
    '2026-10-02 (금)<br>요청 1,234건 · 요청자 5명'
  )
})

test('the chart is one bar per day from zero', () => {
  const option = buildRequestsOption(FORTY.slice(-3))
  const series = option.series as { type: string, data: number[] }[]

  assert.deepEqual((option.xAxis as { data: string[] }).data, ['2026-09-30', '2026-10-01', '2026-10-02'])
  assert.equal(series.length, 1)
  assert.equal(series[0]!.type, 'bar')
  assert.deepEqual(series[0]!.data, [370, 380, 390])
  assert.equal((option.yAxis as { min: number }).min, 0)
})

test('the remainder note says what the feature list leaves out', () => {
  assert.equal(
    requestRemainderNote({ entry: 1200, features: [], other_count: 3 }),
    '목록 외: 장비 목록 진입 1,200건 · Top 10 밖 기능 3건'
  )
  assert.equal(
    requestRemainderNote({ entry: 0, features: [], other_count: 4 }),
    '목록 외: Top 10 밖 기능 4건'
  )
  assert.equal(requestRemainderNote({ entry: 0, features: [], other_count: 0 }), null)
  assert.equal(requestRemainderNote(undefined), null)
})

test('requesters rank by 30-day requests, ties by employee number', () => {
  const rows = topRequesters([
    { user_id: '200', emp_nm: null, dept_nm: null, requests_30d: 5 },
    { user_id: '100', emp_nm: '김철수', dept_nm: '계측팀', requests_30d: 5 },
    { user_id: '300', emp_nm: null, dept_nm: ' ', requests_30d: 9 }
  ])

  assert.deepEqual(rows, [
    { label: '300', hint: '—', count: 9 },
    { label: '김철수', hint: '계측팀', count: 5 },
    { label: '200', hint: '—', count: 5 }
  ])
})
