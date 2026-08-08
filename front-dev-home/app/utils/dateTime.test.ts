import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatDateTimeInput,
  formatDateTimeLocal,
  formatKoreanDateTime,
  shiftIsoDate,
  todayStamp
} from './dateTime.ts'
import { formatDateStamp } from './chartExport.ts'

test('todayStamp agrees with the PNG export stamp', () => {
  // The bug this module exists to close: CSV filenames were built from UTC
  // and PNG filenames from local time, so they disagreed every KST morning.
  assert.equal(todayStamp(), formatDateStamp(new Date()))
})

test('todayStamp is a bare YYYY-MM-DD', () => {
  assert.match(todayStamp(), /^\d{4}-\d{2}-\d{2}$/)
})

test('shiftIsoDate walks back across a month boundary', () => {
  assert.equal(shiftIsoDate('2026-03-02', 3), '2026-02-27')
})

test('shiftIsoDate crosses a leap day', () => {
  assert.equal(shiftIsoDate('2024-03-01', 1), '2024-02-29')
})

test('shiftIsoDate by zero is the identity', () => {
  assert.equal(shiftIsoDate('2026-08-08', 0), '2026-08-08')
})

test('formatDateTimeLocal renders local wall-clock minutes', () => {
  const iso = new Date(2026, 7, 8, 14, 38).toISOString()
  assert.equal(formatDateTimeLocal(iso), '2026-08-08 14:38')
})

test('formatDateTimeLocal can append seconds', () => {
  const iso = new Date(2026, 7, 8, 14, 38, 7).toISOString()
  assert.equal(formatDateTimeLocal(iso, { withSeconds: true }), '2026-08-08 14:38:07')
})

test('formatDateTimeLocal echoes an unparseable input back by default', () => {
  // Visible garbage beats a silently blank cell when the office sends
  // something the mocks never produce.
  assert.equal(formatDateTimeLocal('not-a-date'), 'not-a-date')
})

test('formatDateTimeLocal honours an explicit blank fallback', () => {
  assert.equal(formatDateTimeLocal('not-a-date', { fallback: '' }), '')
  assert.equal(formatDateTimeLocal('', { fallback: '' }), '')
})

test('formatDateTimeInput matches the datetime-local control shape', () => {
  assert.equal(formatDateTimeInput(new Date(2026, 7, 8, 9, 5)), '2026-08-08T09:05')
})

test('formatKoreanDateTime falls back on empty input', () => {
  assert.equal(formatKoreanDateTime(null), '—')
  assert.equal(formatKoreanDateTime(undefined, '-'), '-')
})

test('formatKoreanDateTime uses 24-hour time', () => {
  const iso = new Date(2026, 7, 8, 14, 38).toISOString()
  assert.ok(!/오후|PM/.test(formatKoreanDateTime(iso)))
})
