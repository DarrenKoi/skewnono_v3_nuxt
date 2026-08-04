import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityFeatureLabel, summarizePersonalActivity, pageViewNotice, PAGE_VIEW_SINCE, userDisplayName, userSearchText } from './activity.ts'

test('activityFeatureLabel translates known keys and humanizes unknown keys', () => {
  assert.equal(activityFeatureLabel('recipe_search'), 'Recipe 검색')
  assert.equal(activityFeatureLabel('new_feature'), 'New Feature')
  assert.equal(activityFeatureLabel(null), '—')
})

test('userDisplayName prefers the directory name and falls back to the empno', () => {
  assert.equal(userDisplayName({ user_id: '2067928', emp_nm: '고대영' }), '고대영')
  // No directory row (contractor, service account) or an unreachable directory.
  assert.equal(userDisplayName({ user_id: '2067928', emp_nm: null }), '2067928')
  // A blank name is the same as no name — it must not render an empty cell.
  assert.equal(userDisplayName({ user_id: '2067928', emp_nm: '  ' }), '2067928')
})

test('userSearchText matches on either the name or the employee number', () => {
  const text = userSearchText({ user_id: '2067928', emp_nm: '고대영' })

  assert.ok(text.includes('고대영'))
  assert.ok(text.includes('2067928'))
  // A nameless row is still findable by its id.
  assert.ok(userSearchText({ user_id: '1234567', emp_nm: null }).includes('1234567'))
})

test('summarizePersonalActivity compares the latest two seven-day windows', () => {
  const daily = Array.from({ length: 30 }, (_, index) => ({
    date: `2026-06-${String(index + 1).padStart(2, '0')}`,
    count: index >= 23 ? 4 : index >= 16 ? 2 : 0
  }))

  assert.deepEqual(summarizePersonalActivity(daily), {
    recent7Requests: 28,
    previous7Requests: 14,
    activeDays7: 7,
    averagePerActiveDay30: 3,
    changePercent: 100
  })
})

test('summarizePersonalActivity handles an empty comparison window', () => {
  const daily = Array.from({ length: 7 }, (_, index) => ({
    date: `2026-07-${String(index + 1).padStart(2, '0')}`,
    count: index === 6 ? 3 : 0
  }))

  assert.equal(summarizePersonalActivity(daily).changePercent, null)
  assert.equal(summarizePersonalActivity([]).averagePerActiveDay30, 0)
})

test('the notice shows while the window reaches before collection started', () => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const threeDaysIn = new Date(since.getTime() + 3 * 86_400_000)

  assert.match(pageViewNotice(7, threeDaysIn) ?? '', /2026/)
})

test('the notice disappears once the window is fully covered', () => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const wellAfter = new Date(since.getTime() + 40 * 86_400_000)

  assert.equal(pageViewNotice(7, wellAfter), null)
  assert.equal(pageViewNotice(30, wellAfter), null)
})
