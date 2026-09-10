import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { formatRelativeTime } from './relativeTime.ts'

const now = new Date('2026-07-17T12:00:00Z')

describe('formatRelativeTime', () => {
  it('shows 방금 under a minute', () => {
    assert.equal(formatRelativeTime('2026-07-17T11:59:30Z', now), '방금')
  })

  it('shows minutes', () => {
    assert.equal(formatRelativeTime('2026-07-17T11:45:00Z', now), '15분 전')
  })

  it('shows hours', () => {
    assert.equal(formatRelativeTime('2026-07-17T09:00:00Z', now), '3시간 전')
  })

  it('shows days under a week', () => {
    assert.equal(formatRelativeTime('2026-07-15T12:00:00Z', now), '2일 전')
  })

  it('shows a calendar date beyond a week', () => {
    assert.equal(formatRelativeTime('2026-07-01T12:00:00Z', now), '7월 1일')
  })

  it('returns empty string for an invalid date', () => {
    assert.equal(formatRelativeTime('not-a-date', now), '')
  })
})
