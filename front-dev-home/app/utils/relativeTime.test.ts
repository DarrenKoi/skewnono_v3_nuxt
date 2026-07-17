import { describe, it, expect } from 'vitest'
import { formatRelativeTime } from './relativeTime'

const now = new Date('2026-07-17T12:00:00Z')

describe('formatRelativeTime', () => {
  it('shows 방금 under a minute', () => {
    expect(formatRelativeTime('2026-07-17T11:59:30Z', now)).toBe('방금')
  })

  it('shows minutes', () => {
    expect(formatRelativeTime('2026-07-17T11:45:00Z', now)).toBe('15분 전')
  })

  it('shows hours', () => {
    expect(formatRelativeTime('2026-07-17T09:00:00Z', now)).toBe('3시간 전')
  })

  it('shows days under a week', () => {
    expect(formatRelativeTime('2026-07-15T12:00:00Z', now)).toBe('2일 전')
  })

  it('shows a calendar date beyond a week', () => {
    expect(formatRelativeTime('2026-07-01T12:00:00Z', now)).toBe('7월 1일')
  })

  it('returns empty string for an invalid date', () => {
    expect(formatRelativeTime('not-a-date', now)).toBe('')
  })
})
