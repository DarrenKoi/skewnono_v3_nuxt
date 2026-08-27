// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { workDuration, workEndLabel } from './bmPmWork.ts'

test('workDuration: hours and minutes, dropping a zero minute part', () => {
  assert.equal(workDuration('2026-08-24 08:00', '2026-08-24 17:15'), '9h 15m')
  assert.equal(workDuration('2026-09-04 09:00', '2026-09-04 17:00'), '8h')
  assert.equal(workDuration('2026-07-02 10:30', '2026-07-02 12:05'), '1h 35m')
})

test('workDuration: sub-hour jobs and across-midnight jobs', () => {
  assert.equal(workDuration('2026-07-02 10:30', '2026-07-02 11:15'), '45m')
  assert.equal(workDuration('2026-06-05 22:10', '2026-06-06 02:40'), '4h 30m')
})

test('workDuration: empty for a missing, malformed, or inverted stamp', () => {
  // A tool still down carries no job_end (_shared.py) — not a zero-length job.
  assert.equal(workDuration('2026-07-18 13:00', ''), '')
  assert.equal(workDuration('', '2026-07-18 16:45'), '')
  assert.equal(workDuration('2026-07-18 13:00', 'not-a-date'), '')
  assert.equal(workDuration('2026-07-18 16:45', '2026-07-18 13:00'), '')
})

test('workEndLabel: time only same day, date-prefixed once it crosses midnight', () => {
  assert.equal(workEndLabel('2026-08-24 08:00', '2026-08-24 17:15'), '17:15')
  assert.equal(workEndLabel('2026-06-05 22:10', '2026-06-06 02:40'), '06-06 02:40')
})

test('workEndLabel: empty end stays empty, odd width passes through unsliced', () => {
  assert.equal(workEndLabel('2026-07-18 13:00', ''), '')
  assert.equal(workEndLabel('2026-07-18 13:00', '2026-07-18'), '2026-07-18')
})
