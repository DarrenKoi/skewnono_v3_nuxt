import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityFeatureLabel, summarizePersonalActivity } from './activity.ts'

test('activityFeatureLabel translates known keys and humanizes unknown keys', () => {
  assert.equal(activityFeatureLabel('recipe_search'), 'Recipe 검색')
  assert.equal(activityFeatureLabel('new_feature'), 'New Feature')
  assert.equal(activityFeatureLabel(null), '—')
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
