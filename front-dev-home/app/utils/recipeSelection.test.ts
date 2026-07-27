import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canCompareRecipeSelection,
  capabilitiesForRecipeSelection,
  normalizeRecipeSelectionEntries,
  promoteRecipeSelectionsToRedis,
  recipeNamesForCompare,
  upsertRecipeSelection
} from './recipeSelection.ts'

test('legacy string selections migrate to Redis entries and discard blanks', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([' A ', '', 3, 'B']),
    [
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'redis' }
    ]
  )
})

test('normalization rejects malformed entries and keeps one strongest source per name', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([
      { name: 'A', source: 'opensearch' },
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'wrong' },
      { name: '', source: 'redis' },
      null
    ]),
    [{ name: 'A', source: 'redis' }]
  )
})

test('upsert promotes OpenSearch to Redis and never downgrades Redis', () => {
  const fallback = [{ name: 'A', source: 'opensearch' }] as const
  assert.deepEqual(upsertRecipeSelection([...fallback], 'A', 'redis'), [
    { name: 'A', source: 'redis' }
  ])
  assert.deepEqual(
    upsertRecipeSelection([{ name: 'A', source: 'redis' }], 'A', 'opensearch'),
    [{ name: 'A', source: 'redis' }]
  )
})

test('catalog reconciliation promotes only selected names Redis now contains', () => {
  const selected = [
    { name: 'A', source: 'opensearch' as const },
    { name: 'B', source: 'opensearch' as const }
  ]
  assert.deepEqual(promoteRecipeSelectionsToRedis(selected, ['A', 'C']), [
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ])
})

test('selection capabilities are the intersection across all entries', () => {
  assert.deepEqual(capabilitiesForRecipeSelection([]), {
    open: false,
    lateral: false,
    measHist: false,
    compare: false
  })
  assert.deepEqual(
    capabilitiesForRecipeSelection([{ name: 'A', source: 'redis' }]),
    { open: true, lateral: true, measHist: true, compare: true }
  )
  assert.deepEqual(
    capabilitiesForRecipeSelection([
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'opensearch' }
    ]),
    { open: false, lateral: true, measHist: true, compare: false }
  )
})

test('compare requires at least two selections and every source to be Redis', () => {
  assert.equal(canCompareRecipeSelection([{ name: 'A', source: 'redis' }]), false)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'redis' }
  ]), true)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ]), false)
})

test('compare request names exist only for a Redis-only set of at least two', () => {
  assert.deepEqual(recipeNamesForCompare([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'redis' }
  ]), ['A', 'B'])
  assert.equal(recipeNamesForCompare([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ]), null)
  assert.equal(recipeNamesForCompare([
    { name: 'A', source: 'redis' }
  ]), null)
})
