import { test } from 'node:test'
import assert from 'node:assert/strict'
import { filterRecipeStatusTrendPoints } from './recipeStatusTrend.ts'

const points = [
  { date: '2026-07-25', value: 10 },
  { date: '2026-07-26', value: 20 },
  { date: '2026-07-27', value: 3 }
]

test('filterRecipeStatusTrendPoints excludes only the anchor date by default', () => {
  assert.deepEqual(
    filterRecipeStatusTrendPoints(points, '2026-07-27', false),
    points.slice(0, 2)
  )
})

test('filterRecipeStatusTrendPoints includes the anchor date when enabled', () => {
  assert.deepEqual(
    filterRecipeStatusTrendPoints(points, '2026-07-27', true),
    points
  )
})

test('filterRecipeStatusTrendPoints keeps historical and unanchored ranges intact', () => {
  assert.deepEqual(
    filterRecipeStatusTrendPoints(points, '2026-07-30', false),
    points
  )
  assert.deepEqual(
    filterRecipeStatusTrendPoints(points, undefined, false),
    points
  )
})

test('filterRecipeStatusTrendPoints does not mutate its input', () => {
  const input = points.map(point => ({ ...point }))
  const before = structuredClone(input)

  filterRecipeStatusTrendPoints(input, '2026-07-27', false)

  assert.deepEqual(input, before)
})
