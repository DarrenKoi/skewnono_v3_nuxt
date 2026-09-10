import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  addRecipeRecentSearch,
  normalizeRecipeRecentSearches,
  recipeRecentSearchKey
} from './recipeRecentSearches.ts'

test('an entry remembers the fabs it was searched in', () => {
  const list = addRecipeRecentSearch([], { term: 'ABC_X', fabs: ['R3'] }, 10)
  assert.deepEqual(list, [{ term: 'ABC_X', fabs: ['R3'] }])
})

test('same term in a different fab is a distinct entry; same pair is deduped to the front', () => {
  let list = addRecipeRecentSearch([], { term: 'ABC_X', fabs: ['R3'] }, 10)
  list = addRecipeRecentSearch(list, { term: 'ABC_X', fabs: ['M16B'] }, 10)
  assert.equal(list.length, 2)
  list = addRecipeRecentSearch(list, { term: 'abc_x', fabs: ['R3'] }, 10)
  assert.equal(list.length, 2)
  assert.equal(recipeRecentSearchKey(list[0]!), 'abc_x@R3')
})

test('legacy v2 string entries survive with no fab; malformed entries are dropped', () => {
  const parsed = normalizeRecipeRecentSearches(['OLD_TERM', { term: 'NEW', fabs: ['m16b', 'M16B'] }, { fabs: ['R3'] }, 42])
  assert.deepEqual(parsed, [
    { term: 'OLD_TERM', fabs: [] },
    { term: 'NEW', fabs: ['M16B'] }
  ])
})
