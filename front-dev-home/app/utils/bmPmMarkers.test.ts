// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseBmPmEvents, bmPmMarkLine } from './bmPmMarkers.ts'

const tables = [
  {
    key: 'past_work',
    rows: [
      { timestamp: '2026-07-01 12:30', eqp_id: 'ECX101', category: 'PM', job_starts: '2026-07-01 08:00', job_end: '2026-07-01 12:00', engr_note: '정기 점검.' },
      { timestamp: '2026-06-20 10:00', eqp_id: 'ECX101', category: 'BM', job_starts: '2026-06-20 07:00', job_end: '2026-06-20 09:30', engr_note: '<스테이지> 교체.' }
    ]
  },
  {
    key: 'future_work',
    rows: [
      { category: 'PM', job_starts: '2026-08-01 08:00', job_end: '2026-08-01 16:00', timestamp: '2026-07-10 09:00' }
    ]
  }
]

test('parseBmPmEvents: maps past_work rows only', () => {
  const events = parseBmPmEvents(tables)
  assert.equal(events.length, 2)
  assert.deepEqual(events[0], {
    ts: '2026-07-01 08:00',
    category: 'PM',
    jobEnd: '2026-07-01 12:00',
    note: '정기 점검.'
  })
})

test('parseBmPmEvents: unknown category or missing start → dropped', () => {
  const events = parseBmPmEvents([
    {
      key: 'past_work',
      rows: [
        { category: 'ETC', job_starts: '2026-07-01 08:00' },
        { category: 'BM', job_starts: '' },
        { category: 'BM', job_starts: '2026-07-02 08:00', job_end: '2026-07-02 10:00', engr_note: 'ok' }
      ]
    }
  ])
  assert.equal(events.length, 1)
  assert.equal(events[0]!.category, 'BM')
})

test('parseBmPmEvents: no past_work table → empty', () => {
  assert.deepEqual(parseBmPmEvents([]), [])
  assert.deepEqual(parseBmPmEvents([{ key: 'future_work', rows: [] }]), [])
})

test('bmPmMarkLine: one dashed vertical line per event at the job-start epoch', () => {
  const mk = bmPmMarkLine(parseBmPmEvents(tables))!
  assert.equal(mk.data.length, 2)
  assert.equal(mk.data[0]!.xAxis, new Date('2026-07-01T08:00').getTime())
  assert.equal(mk.data[0]!.label.formatter, 'PM')
  assert.equal(mk.lineStyle.type, 'dashed')
  assert.equal(mk.symbol, 'none')
})

test('bmPmMarkLine: BM/PM colors differ, and light/dark pairs differ', () => {
  const events = parseBmPmEvents(tables)
  const light = bmPmMarkLine(events)!
  const dark = bmPmMarkLine(events, { dark: true })!
  assert.notEqual(light.data[0]!.lineStyle.color, light.data[1]!.lineStyle.color)
  assert.notEqual(light.data[0]!.lineStyle.color, dark.data[0]!.lineStyle.color)
})

test('bmPmMarkLine: tooltip carries the job window and HTML-escaped note', () => {
  const mk = bmPmMarkLine(parseBmPmEvents(tables))!
  const bm = mk.data.find(d => d.label.formatter === 'BM')!
  assert.ok(bm.tooltip.formatter.includes('2026-06-20 07:00'))
  assert.ok(bm.tooltip.formatter.includes('&lt;스테이지&gt;'))
})

test('bmPmMarkLine: empty events → undefined', () => {
  assert.equal(bmPmMarkLine([]), undefined)
})
