import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildRecipeDetailNavItems } from './recipeView.ts'

test('creates all detail hops and marks the active screen', () => {
  const items = buildRecipeDetailNavItems(
    'cd-sem', 'R3', 'RECIPE-01', 'lateral', undefined
  )
  assert.deepEqual(items.map(item => item.label), [
    '열어 보기', '횡전개', '측정 이력'
  ])
  assert.deepEqual(items.map(item => item.active), [false, true, false])
  assert.deepEqual(items[0]?.to, {
    path: '/ebeam/cd-sem/r3/recipe-search/open',
    query: { recipe_name: 'RECIPE-01' }
  })
})

test('preserves the work-set flag on every hop', () => {
  const items = buildRecipeDetailNavItems(
    'hv-sem', 'R4', 'HV-RECIPE', 'open', '1'
  )
  assert.deepEqual(items.map(item => item.to.query), [
    { recipe_name: 'HV-RECIPE', set: '1' },
    { recipe_name: 'HV-RECIPE', set: '1' },
    { recipe_name: 'HV-RECIPE', set: '1' }
  ])
})

test('carries the owner fab on every hop, keeping the multi-fab path segment', () => {
  const items = buildRecipeDetailNavItems(
    'cd-sem', 'r3,m16b', 'RECIPE-01', 'lateral', undefined, 'redis', 'm16b'
  )
  assert.deepEqual(items.map(item => item.to.path), [
    '/ebeam/cd-sem/r3,m16b/recipe-search/open',
    '/ebeam/cd-sem/r3,m16b/recipe-search/lateral',
    '/ebeam/cd-sem/r3,m16b/recipe-search/meas-hist'
  ])
  for (const item of items) {
    assert.deepEqual(item.to.query, { recipe_name: 'RECIPE-01', fab_name: 'M16B' })
  }
})

test('omits the fab_name query when no owner fab is given', () => {
  const items = buildRecipeDetailNavItems(
    'cd-sem', 'R3', 'RECIPE-01', 'open', undefined
  )
  for (const item of items) assert.equal('fab_name' in item.to.query, false)
})
