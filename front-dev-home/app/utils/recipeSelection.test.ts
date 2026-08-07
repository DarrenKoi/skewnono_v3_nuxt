import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canCompareRecipeSelection,
  capabilitiesForRecipeSelection,
  normalizeRecipeSelectionEntries,
  promoteRecipeSelectionsToRedis,
  recipesForCompare,
  removeRecipeSelection,
  upsertRecipeSelection,
  type RecipeSelectionEntry
} from './recipeSelection.ts'

test('legacy string selections migrate to Redis entries and discard blanks', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([' A ', '', 3, 'B']),
    [
      { name: 'A', fab_name: '', source: 'redis' },
      { name: 'B', fab_name: '', source: 'redis' }
    ]
  )
})

test('normalization rejects malformed entries and keeps one strongest source per (name, fab)', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([
      { name: 'A', fab_name: 'R3', source: 'opensearch' },
      { name: 'A', fab_name: 'R3', source: 'redis' },
      { name: 'B', fab_name: 'R3', source: 'wrong' },
      { name: '', fab_name: 'R3', source: 'redis' },
      null
    ]),
    [{ name: 'A', fab_name: 'R3', source: 'redis' }]
  )
})

test('upsert promotes OpenSearch to Redis and never downgrades Redis', () => {
  const fallback = [{ name: 'A', fab_name: 'R3', source: 'opensearch' }] as const
  assert.deepEqual(upsertRecipeSelection([...fallback], 'A', 'R3', 'redis'), [
    { name: 'A', fab_name: 'R3', source: 'redis' }
  ])
  assert.deepEqual(
    upsertRecipeSelection([{ name: 'A', fab_name: 'R3', source: 'redis' }], 'A', 'R3', 'opensearch'),
    [{ name: 'A', fab_name: 'R3', source: 'redis' }]
  )
})

test('same name in two fabs are two distinct selections', () => {
  let entries: RecipeSelectionEntry[] = []
  entries = upsertRecipeSelection(entries, 'A/B_1', 'R3', 'redis')
  entries = upsertRecipeSelection(entries, 'A/B_1', 'M16B', 'redis')
  assert.equal(entries.length, 2)
  entries = removeRecipeSelection(entries, 'A/B_1', 'R3')
  assert.deepEqual(entries, [{ name: 'A/B_1', fab_name: 'M16B', source: 'redis' }])
})

test('catalog reconciliation promotes only selected names Redis now contains', () => {
  const selected = [
    { name: 'A', fab_name: '', source: 'opensearch' as const },
    { name: 'B', fab_name: '', source: 'opensearch' as const }
  ]
  assert.deepEqual(
    promoteRecipeSelectionsToRedis(selected, [{ recipe_name: 'A', fab_name: 'R3' }]),
    [
      { name: 'A', fab_name: 'R3', source: 'redis' },
      { name: 'B', fab_name: '', source: 'opensearch' }
    ]
  )
})

test('promotion adopts the catalog row fab and dedupes', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'X', fab_name: '', source: 'opensearch' },
    { name: 'X', fab_name: 'R3', source: 'redis' }
  ]
  const next = promoteRecipeSelectionsToRedis(entries, [{ recipe_name: 'X', fab_name: 'R3' }])
  assert.deepEqual(next, [{ name: 'X', fab_name: 'R3', source: 'redis' }])
})

test('selection capabilities are the intersection across all entries', () => {
  assert.deepEqual(capabilitiesForRecipeSelection([]), {
    open: false,
    lateral: false,
    measHist: false,
    compare: false
  })
  assert.deepEqual(
    capabilitiesForRecipeSelection([{ name: 'A', fab_name: 'R3', source: 'redis' }]),
    { open: true, lateral: true, measHist: true, compare: true }
  )
  assert.deepEqual(
    capabilitiesForRecipeSelection([
      { name: 'A', fab_name: 'R3', source: 'redis' },
      { name: 'B', fab_name: 'R3', source: 'opensearch' }
    ]),
    { open: false, lateral: true, measHist: true, compare: false }
  )
})

test('compare requires at least two selections and every source to be Redis', () => {
  assert.equal(canCompareRecipeSelection([{ name: 'A', fab_name: 'R3', source: 'redis' }]), false)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', fab_name: 'R3', source: 'redis' },
    { name: 'B', fab_name: 'R3', source: 'redis' }
  ]), true)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', fab_name: 'R3', source: 'redis' },
    { name: 'B', fab_name: 'R3', source: 'opensearch' }
  ]), false)
})

test('recipesForCompare returns (name, fab) pairs', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'A', fab_name: 'R3', source: 'redis' },
    { name: 'A', fab_name: 'M16B', source: 'redis' }
  ]
  assert.deepEqual(recipesForCompare(entries), [
    { recipe_name: 'A', fab_name: 'R3' },
    { recipe_name: 'A', fab_name: 'M16B' }
  ])
})

test('recipesForCompare rejects a set with any OpenSearch member', () => {
  assert.equal(recipesForCompare([
    { name: 'A', fab_name: 'R3', source: 'redis' },
    { name: 'B', fab_name: 'R3', source: 'opensearch' }
  ]), null)
  assert.equal(recipesForCompare([
    { name: 'A', fab_name: 'R3', source: 'redis' }
  ]), null)
})

test('recipesForCompare rejects a multi-entry OpenSearch-only set', () => {
  assert.equal(recipesForCompare([
    { name: 'A', fab_name: '', source: 'opensearch' },
    { name: 'B', fab_name: '', source: 'opensearch' }
  ]), null)
})
