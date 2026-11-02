import assert from 'node:assert/strict'
import test from 'node:test'
import type { EndpointDay } from '~/composables/useActivityApi'
import { OTHER_ENDPOINTS, UNATTRIBUTED, buildEndpointsOption, endpointKpis, topCallers, topEndpoints } from './activityEndpoints.ts'

const DAYS: EndpointDay[] = [
  { date: '2026-11-01', requests: 10, endpoints: { 'GET /api/a': 6, 'POST /api/b': 4 }, users: { u1: 7 } },
  { date: '2026-11-02', requests: 5, endpoints: { 'GET /api/a': 1, 'GET /api/c': 4 }, users: { u1: 1, u2: 2 } }
]

test('endpoints are summed over the window and split into path and method', () => {
  assert.deepEqual(topEndpoints(DAYS), [
    { label: '/api/a', hint: 'GET', title: 'GET /api/a', count: 7 },
    { label: '/api/c', hint: 'GET', title: 'GET /api/c', count: 4 },
    { label: '/api/b', hint: 'POST', title: 'POST /api/b', count: 4 }
  ])
})

test('calls with no user become one ranked unattributed row', () => {
  const rows = topCallers(DAYS, { u1: { emp_nm: '홍길동', dept_nm: '계측팀' } })
  assert.deepEqual(rows.map(row => [row.label, row.count]), [['홍길동', 8], [UNATTRIBUTED, 5], ['u2', 2]])
})

test('the stacked bands add up to each day total', () => {
  const option = buildEndpointsOption(DAYS)
  const bands = option.series as { name: string, data: number[] }[]
  assert.equal(bands.at(-1)!.name, OTHER_ENDPOINTS)
  for (const [index, day] of DAYS.entries()) {
    assert.equal(bands.reduce((total, band) => total + band.data[index]!, 0), day.requests)
  }
})

test('KPIs read today and the trailing windows from the one series', () => {
  const [today, week] = endpointKpis(DAYS)
  assert.equal(today!.value, '5')
  assert.equal(week!.value, '15')
})
