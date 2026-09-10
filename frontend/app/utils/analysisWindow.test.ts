// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_WINDOW_WEEKS,
  WINDOW_WEEKS,
  isWindowWeeks,
  normalizeWindowWeeks,
  windowDays,
  windowLabel
} from './analysisWindow.ts'

test('the choices are exactly what the server accepts, and the default is one of them', () => {
  assert.deepEqual([...WINDOW_WEEKS], [1, 2, 3, 4])
  assert.ok(isWindowWeeks(DEFAULT_WINDOW_WEEKS))
})

test('normalizeWindowWeeks keeps a valid choice', () => {
  for (const weeks of WINDOW_WEEKS) assert.equal(normalizeWindowWeeks(weeks), weeks)
})

test('normalizeWindowWeeks falls back for anything the server would 400', () => {
  // A stored value is user-writable and survives deploys: a number outside the
  // choices, a numeric STRING (JSON round-trips preserve type, but a hand edit
  // does not), an entry written before the field existed.
  for (const raw of [0, 5, 8, 1.5, '2', null, undefined, {}]) {
    assert.equal(normalizeWindowWeeks(raw), DEFAULT_WINDOW_WEEKS, String(raw))
  }
})

test('windowDays and windowLabel read off the same number', () => {
  assert.equal(windowDays(3), 21)
  assert.equal(windowLabel(3), '3주 윈도우')
})
