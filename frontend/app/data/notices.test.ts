// Run: node --test app/data/notices.test.ts
// useNotices compares dates as strings and treats NOTICES[0] as the newest, so a
// hand-typed '2026-9-18' or an entry appended at the bottom would silently break the
// header's N badge. This pins both.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { NOTICES } from './notices.ts'

test('dates are ISO YYYY-MM-DD, unique, newest first', () => {
  for (const notice of NOTICES) {
    assert.match(notice.date, /^\d{4}-\d{2}-\d{2}$/, `${notice.title}: ${notice.date}`)
    assert.ok(notice.items.length > 0, `${notice.date} has no items`)
  }
  const dates = NOTICES.map(notice => notice.date)
  assert.deepEqual(dates, [...new Set(dates)].sort().reverse())
})
