import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  activeRecipeResults,
  isRecipeQueryEligible,
  matchesRecipeQuery,
  matchingHistoryNames,
  normalizeRecipeNameSnapshot,
  rankRecipeMatches,
  resolveRecipeSearchViewState,
  shouldProbeRecipeFallback,
  toRecipeSearchResults,
  tokenizeRecipeQuery
} from './recipeSearchMatch.ts'

const NAME = 'ADI/CD_BIAS_ABC123_MON_00005'.toLowerCase()

const matches = (query: string) => matchesRecipeQuery(NAME, tokenizeRecipeQuery(query))

test('tokenize splits on whitespace and underscores, lowercased', () => {
  assert.deepEqual(tokenizeRecipeQuery('CD_BIAS MON'), ['cd', 'bias', 'mon'])
})

test('tokenize drops empty fragments from repeated separators', () => {
  assert.deepEqual(tokenizeRecipeQuery('  _cd__bias_  '), ['cd', 'bias'])
})

test('tokenize returns no tokens for blank or separator-only input', () => {
  assert.deepEqual(tokenizeRecipeQuery(''), [])
  assert.deepEqual(tokenizeRecipeQuery(' _ _ '), [])
})

test('query eligibility rejects blank and separator-only input', () => {
  assert.equal(isRecipeQueryEligible(''), false)
  assert.equal(isRecipeQueryEligible('   '), false)
  assert.equal(isRecipeQueryEligible('___'), false)
  assert.equal(isRecipeQueryEligible(' _ _ '), false)
})

test('query eligibility counts meaningful characters instead of separator padding', () => {
  assert.equal(isRecipeQueryEligible('a__'), false)
  assert.equal(isRecipeQueryEligible('__ab__'), false)
  assert.equal(isRecipeQueryEligible('_a_b_'), false)
})

test('query eligibility accepts three or more meaningful characters across tokens', () => {
  assert.equal(isRecipeQueryEligible('abc'), true)
  assert.equal(isRecipeQueryEligible('a_b_c'), true)
  assert.equal(isRecipeQueryEligible('__a_bc__'), true)
})

test('every contiguous-substring match keeps working (relaxation guarantee)', () => {
  assert.equal(matches('CD_BIAS'), true)
  assert.equal(matches('abc123'), true)
  assert.equal(matches('ADI/CD'), true)
})

test('matches across underscore segment boundaries', () => {
  // The old contiguous includes('ADI_MON') returned nothing for NAME.
  assert.equal(matches('ADI_MON'), true)
})

test('matches segments regardless of order', () => {
  assert.equal(matches('MON_CD'), true)
  assert.equal(matches('mon bias adi'), true)
})

test('still rejects names missing any token', () => {
  assert.equal(matches('CD_BIAS_GATE'), false)
  assert.equal(matches('MONITOR'), false)
})

test('never matches on an empty token list', () => {
  assert.equal(matchesRecipeQuery(NAME, []), false)
})

test('ranks exact, prefix, substring and token-only matches while preserving ties', () => {
  const exactName = 'RJ1BXXX_CG6300/RJ1B_SN2SP_M_SE'
  const query = exactName.toLowerCase()
  const names = [
    `PREFIX_${exactName}`,
    `Z_SE_M_SN2SP_${exactName.split('_').slice(0, 2).join('_')}`,
    `A_SE_M_SN2SP_${exactName.split('_').slice(0, 2).join('_')}`,
    `${exactName}_BACKUP`,
    exactName
  ]

  assert.deepEqual(
    rankRecipeMatches(
      names.map(name => ({ value: name, searchText: name.toLowerCase() })),
      query
    ),
    [
      exactName,
      `${exactName}_BACKUP`,
      `PREFIX_${exactName}`,
      `Z_SE_M_SN2SP_${exactName.split('_').slice(0, 2).join('_')}`,
      `A_SE_M_SN2SP_${exactName.split('_').slice(0, 2).join('_')}`
    ]
  )
})

test('history names re-apply AND semantics over the server OR results', () => {
  const tokens = tokenizeRecipeQuery('CD_MON')
  // The server ORs terms, so rows matching only "cd" or only "mon" come back.
  const rows = [
    'ADI/CD_BIAS_ABC123_STD_00001',
    'ETC/GATE_MON_ABC123_STD_00002',
    'ADI/CD_MON_ABC123_ENG_00003'
  ]
  assert.deepEqual(matchingHistoryNames(rows, tokens), ['ADI/CD_MON_ABC123_ENG_00003'])
})

test('history names are deduped, preserving first-seen order', () => {
  const tokens = tokenizeRecipeQuery('CD')
  const rows = ['ADI/CD_A', 'ADI/CD_B', 'ADI/CD_A']
  assert.deepEqual(matchingHistoryNames(rows, tokens), ['ADI/CD_A', 'ADI/CD_B'])
})

test('history names are empty for an empty token list', () => {
  assert.deepEqual(matchingHistoryNames(['ADI/CD_A'], []), [])
})

test('recipe-name snapshot uses raw rows when additive fields are unavailable', () => {
  const rows = [{ full_name: 'RAW/A' }, { full_name: 'RAW/B' }]

  assert.deepEqual(normalizeRecipeNameSnapshot({ rows }), {
    names: ['RAW/A', 'RAW/B'],
    complete: false
  })
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: 'not-an-array',
    recipe_names_complete: true,
    rows
  }), {
    names: ['RAW/A', 'RAW/B'],
    complete: false
  })
})

test('recipe-name snapshot uses raw rows when an array has no valid members', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [null],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A' }, { full_name: 'RAW/B' }]
  }), {
    names: ['RAW/A', 'RAW/B'],
    complete: false
  })
})

test('recipe-name snapshot merges valid partial members with raw rows', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: ['SNAPSHOT/A', null, 'SNAPSHOT/B'],
    recipe_names_complete: true,
    rows: [
      { full_name: 'RAW/A' },
      { full_name: 'SNAPSHOT/A' }
    ]
  }), {
    names: ['SNAPSHOT/A', 'SNAPSHOT/B', 'RAW/A'],
    complete: false
  })
})

test('recipe-name snapshot removes blanks and duplicates from partial data', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: ['SNAPSHOT/A', '', 'SNAPSHOT/A'],
    recipe_names_complete: true,
    rows: [
      { full_name: 'SNAPSHOT/A' },
      { full_name: 'RAW/A' },
      { full_name: ' ' },
      { full_name: 'RAW/A' }
    ]
  }), {
    names: ['SNAPSHOT/A', 'RAW/A'],
    complete: false
  })
})

test('recipe-name snapshot preserves an intentionally empty complete array', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A' }]
  }), {
    names: [],
    complete: true
  })
})

test('recipe-name snapshot preserves fully valid names', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: ['SNAPSHOT/B', 'SNAPSHOT/A'],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A' }]
  }), {
    names: ['SNAPSHOT/B', 'SNAPSHOT/A'],
    complete: true
  })
})

test('fallback probing waits for Redis and runs only for a searchable zero match', () => {
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: false, redisMatchCount: 0
  }), true)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: true, redisMatchCount: 0
  }), false)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: false, redisMatchCount: 1
  }), false)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: false, catalogPending: false, redisMatchCount: 0
  }), false)
})

test('separator-only input cannot become eligible for fallback probing', () => {
  const canSearch = isRecipeQueryEligible('___')

  assert.equal(canSearch, false)
  assert.equal(shouldProbeRecipeFallback({
    canSearch,
    catalogPending: false,
    redisMatchCount: 0
  }), false)
})

test('source-aware results dedupe names and Redis results always win', () => {
  const redis = toRecipeSearchResults(['A', 'B'], 'redis')
  const fallback = toRecipeSearchResults(['B', 'C', 'C'], 'opensearch')
  assert.deepEqual(fallback, [
    { recipe_name: 'B', source: 'opensearch' },
    { recipe_name: 'C', source: 'opensearch' }
  ])
  assert.equal(activeRecipeResults(redis, fallback), redis)
  assert.equal(activeRecipeResults([], fallback), fallback)
})

test('view state distinguishes fallback loading, results, empty and both-source failure', () => {
  const base = {
    canSearch: true,
    catalogPending: false,
    catalogFailed: false,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false,
    fallbackTruncated: false
  }
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackPending: true
  }), 'fallback-loading')
  assert.equal(resolveRecipeSearchViewState({
    ...base, resultCount: 2
  }), 'results')
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackSettled: true
  }), 'empty')
  assert.equal(resolveRecipeSearchViewState({
    ...base, catalogFailed: true, fallbackSettled: true, fallbackFailed: true
  }), 'sources-error')
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackSettled: true, fallbackFailed: true
  }), 'fallback-error')
  assert.equal(resolveRecipeSearchViewState({
    ...base, catalogPending: true, resultCount: 2
  }), 'results')
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackSettled: true, fallbackTruncated: true
  }), 'fallback-incomplete')
})

test('view state preserves catalog loading and pre-search idle behavior', () => {
  assert.equal(resolveRecipeSearchViewState({
    canSearch: true,
    catalogPending: true,
    catalogFailed: false,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false,
    fallbackTruncated: false
  }), 'catalog-loading')
  assert.equal(resolveRecipeSearchViewState({
    canSearch: false,
    catalogPending: false,
    catalogFailed: true,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false,
    fallbackTruncated: false
  }), 'idle')
})

test('view state keeps an empty query idle while the catalog is pending', () => {
  assert.equal(resolveRecipeSearchViewState({
    canSearch: false,
    catalogPending: true,
    catalogFailed: false,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false,
    fallbackTruncated: false
  }), 'idle')
})
