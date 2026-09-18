// Run: node --test app/utils/noticeFilter.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Notice } from '../data/notices.ts'
import { groupNoticesByMonth, matchesNotice, type NoticeFilter } from './noticeFilter.ts'

const notice = (date: string, overrides: Partial<Notice> = {}): Notice => ({
  date,
  category: '기능추가',
  title: '제목',
  sections: [{ area: '스큐보아', items: ['갤러리 뷰어'] }],
  ...overrides
})

const none: NoticeFilter = { query: '', category: null, area: null, unreadAfter: null }

test('every filter narrows independently, and an empty filter passes everything', () => {
  const n = notice('2026-09-10')
  assert.ok(matchesNotice(n, none))
  assert.ok(!matchesNotice(n, { ...none, category: '공지' }))
  assert.ok(!matchesNotice(n, { ...none, area: 'H/W 관리' }))
  assert.ok(matchesNotice(n, { ...none, area: '스큐보아' }))
})

test('unread means strictly after the last-seen date', () => {
  const n = notice('2026-09-10')
  assert.ok(matchesNotice(n, { ...none, unreadAfter: '' }))
  assert.ok(matchesNotice(n, { ...none, unreadAfter: '2026-09-09' }))
  assert.ok(!matchesNotice(n, { ...none, unreadAfter: '2026-09-10' }))
})

test('search reads item text, case-insensitively and trimmed', () => {
  const n = notice('2026-09-10', { sections: [{ area: '스큐보아', items: ['MSR 원본을 내려받습니다'] }] })
  assert.ok(matchesNotice(n, { ...none, query: '  msr ' }))
  assert.ok(!matchesNotice(n, { ...none, query: 'TTTM' }))
})

test('months group in input order', () => {
  const months = groupNoticesByMonth([notice('2026-09-18'), notice('2026-09-01'), notice('2026-08-28')])
  assert.deepEqual(months.map(m => [m.label, m.notices.length]), [['2026년 9월', 2], ['2026년 8월', 1]])
})
