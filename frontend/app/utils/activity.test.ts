import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityFeatureLabel, pageViewNotice, PAGE_VIEW_SINCE, rankableFabRows, FABLESS_BUCKET, userDisplayName, userSearchText, userTeamLabel } from './activity.ts'

/** A listed row's identity fields, with the directory having answered fully. */
const listed = (over = {}) => ({
  user_id: '2067928',
  emp_nm: '고대영',
  dept_nm: '계측기술팀',
  ...over
})

test('activityFeatureLabel translates known keys and humanizes unknown keys', () => {
  assert.equal(activityFeatureLabel('recipe_search'), 'Recipe 검색')
  assert.equal(activityFeatureLabel('new_feature'), 'New Feature')
  assert.equal(activityFeatureLabel(null), '—')
})

test('userDisplayName prefers the directory name and falls back to the empno', () => {
  assert.equal(userDisplayName(listed()), '고대영')
  // No directory row (contractor, service account) or an unreachable directory.
  assert.equal(userDisplayName(listed({ emp_nm: null })), '2067928')
  // A blank name is the same as no name — it must not render an empty cell.
  assert.equal(userDisplayName(listed({ emp_nm: '  ' })), '2067928')
})

test('userTeamLabel dashes when the directory had no team', () => {
  assert.equal(userTeamLabel(listed()), '계측기술팀')
  assert.equal(userTeamLabel(listed({ dept_nm: null })), '—')
  assert.equal(userTeamLabel(listed({ dept_nm: '  ' })), '—')
  // A member document may be partial, so the two fields fall back separately.
  assert.equal(userTeamLabel(listed({ emp_nm: null })), '계측기술팀')
})

test('userSearchText matches on the name, the employee number or the team', () => {
  const text = userSearchText(listed())

  assert.ok(text.includes('고대영'))
  assert.ok(text.includes('2067928'))
  assert.ok(text.includes('계측기술팀'))
  // A row the directory knows nothing about is still findable by its id.
  const bare = userSearchText(listed({ user_id: '1234567', emp_nm: null, dept_nm: null }))
  assert.ok(bare.includes('1234567'))
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

test('rankableFabRows drops the fab-less bucket and preserves order', () => {
  const rows = [{ fab: 'M14' }, { fab: FABLESS_BUCKET }, { fab: 'R3' }]

  assert.deepEqual(rankableFabRows(rows), [{ fab: 'M14' }, { fab: 'R3' }])
})

test('rankableFabRows is a no-op when the backend sent no fab-less bucket', () => {
  const rows = [{ fab: 'M14' }, { fab: 'R3' }]

  assert.deepEqual(rankableFabRows(rows), rows)
})

test('rankableFabRows can empty the list entirely', () => {
  // A window in which only fab-less pages were used. The card must render its
  // empty state, not a one-row chart of nothing.
  assert.deepEqual(rankableFabRows([{ fab: FABLESS_BUCKET }]), [])
})
