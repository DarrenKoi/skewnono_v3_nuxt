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

// 승격은 (recipe_name, fab_name) 쌍으로 맞춥니다. 이름만 보고 카탈로그 첫 행의
// fab을 채택하면, R3∩M16B 이름 중복(약 20%)에서 선택 항목이 조용히 다른 fab으로
// 재라우팅됩니다 — 비교 본문과 `&fab_name=` 소유 fab이 함께 어긋납니다.
test('promotion never rewrites an entry fab to another fab that shares the name', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'SHARED', fab_name: 'M16B', source: 'opensearch' },
    { name: 'SHARED', fab_name: 'R3', source: 'opensearch' }
  ]
  const next = promoteRecipeSelectionsToRedis(entries, [
    { recipe_name: 'SHARED', fab_name: 'R3' },
    { recipe_name: 'SHARED', fab_name: 'M16B' }
  ])
  assert.deepEqual(next, [
    { name: 'SHARED', fab_name: 'M16B', source: 'redis' },
    { name: 'SHARED', fab_name: 'R3', source: 'redis' }
  ])
})

test('an entry whose own fab has no catalog row is not promoted by another fab row', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'SHARED', fab_name: 'M16B', source: 'opensearch' }
  ]
  assert.deepEqual(
    promoteRecipeSelectionsToRedis(entries, [{ recipe_name: 'SHARED', fab_name: 'R3' }]),
    entries
  )
})

// fab 미상 항목만 이름 전용 조회를 씁니다. 이름이 두 fab에 걸치면 추측하지 않고
// 자기 fab('')을 그대로 둡니다 — 틀린 fab을 채우는 것보다 미상이 낫습니다.
test('a fab-unknown entry is left alone when the name maps to more than one fab', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'SHARED', fab_name: '', source: 'opensearch' }
  ]
  assert.deepEqual(
    promoteRecipeSelectionsToRedis(entries, [
      { recipe_name: 'SHARED', fab_name: 'R3' },
      { recipe_name: 'SHARED', fab_name: 'M16B' }
    ]),
    entries
  )
})

test('pair matching is case-insensitive on fab, like every other fab comparison', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'A', fab_name: 'R3', source: 'opensearch' }
  ]
  assert.deepEqual(
    promoteRecipeSelectionsToRedis(entries, [{ recipe_name: 'A', fab_name: 'r3' }]),
    [{ name: 'A', fab_name: 'R3', source: 'redis' }]
  )
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
