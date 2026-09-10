import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  capabilitiesForRecipeSelection,
  promoteRecipeSelectionsToRedis
} from './recipeSelection.ts'
import {
  activeRecipeResults,
  isRecipeQueryEligible,
  matchesRecipeQuery,
  matchingHistoryPairs,
  confirmedRegistryPairs,
  normalizeRecipeNameSnapshot,
  promoteVerifiedResults,
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

const pair = (recipe_name: string, fab_name = '') => ({ recipe_name, fab_name })

test('history pairs re-apply AND semantics over the server OR results', () => {
  const tokens = tokenizeRecipeQuery('CD_MON')
  // The server ORs terms, so pairs matching only "cd" or only "mon" come back.
  const pairs = [
    pair('ADI/CD_BIAS_ABC123_STD_00001', 'R3'),
    pair('ETC/GATE_MON_ABC123_STD_00002', 'R3'),
    pair('ADI/CD_MON_ABC123_ENG_00003', 'M16B')
  ]
  assert.deepEqual(
    matchingHistoryPairs(pairs, tokens),
    [pair('ADI/CD_MON_ABC123_ENG_00003', 'M16B')]
  )
})

test('history pairs are deduped by (name, fab), preserving first-seen order', () => {
  const tokens = tokenizeRecipeQuery('CD')
  const pairs = [pair('ADI/CD_A', 'R3'), pair('ADI/CD_B', 'R3'), pair('ADI/CD_A', 'R3')]
  assert.deepEqual(
    matchingHistoryPairs(pairs, tokens),
    [pair('ADI/CD_A', 'R3'), pair('ADI/CD_B', 'R3')]
  )
})

test('history pairs keep both fab copies of a duplicate name', () => {
  const tokens = tokenizeRecipeQuery('CD')
  const pairs = [pair('ADI/CD_A', 'R3'), pair('ADI/CD_A', 'M16B')]
  assert.deepEqual(
    matchingHistoryPairs(pairs, tokens),
    [pair('ADI/CD_A', 'R3'), pair('ADI/CD_A', 'M16B')]
  )
})

test('history pairs are empty for an empty token list', () => {
  assert.deepEqual(matchingHistoryPairs([pair('ADI/CD_A', 'R3')], []), [])
})

test('recipe-name snapshot uses raw rows when snapshot fields are unavailable', () => {
  const rows = [
    { full_name: 'RAW/A', fab_name: 'R3' },
    { full_name: 'RAW/B', fab_name: 'M16B' }
  ]

  assert.deepEqual(normalizeRecipeNameSnapshot({ rows }), {
    pairs: [pair('RAW/A', 'R3'), pair('RAW/B', 'M16B')],
    complete: false
  })
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: 'not-an-array',
    recipe_names_complete: true,
    rows
  }), {
    pairs: [pair('RAW/A', 'R3'), pair('RAW/B', 'M16B')],
    complete: false
  })
})

test('recipe-name snapshot uses raw rows when an array has no valid members', () => {
  // A row without a usable fab still names the recipe — owner unknown.
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [null],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A', fab_name: 'R3' }, { full_name: 'RAW/B' }]
  }), {
    pairs: [pair('RAW/A', 'R3'), pair('RAW/B', '')],
    complete: false
  })
})

test('recipe-name snapshot merges valid partial members with raw rows', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [
      { full_name: 'SNAPSHOT/A', fab_name: 'R3' },
      null,
      { full_name: 'SNAPSHOT/B', fab_name: 'M16B' }
    ],
    recipe_names_complete: true,
    rows: [
      { full_name: 'RAW/A', fab_name: 'R3' },
      { full_name: 'SNAPSHOT/A', fab_name: 'R3' }
    ]
  }), {
    pairs: [pair('SNAPSHOT/A', 'R3'), pair('SNAPSHOT/B', 'M16B'), pair('RAW/A', 'R3')],
    complete: false
  })
})

test('recipe-name snapshot removes blanks and duplicates from partial data', () => {
  // The lowercase 'r3' copy normalizes to the same (name, fab) pair and the
  // blank full_name entry is invalid, forcing the merge-with-rows path.
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [
      { full_name: 'SNAPSHOT/A', fab_name: 'R3' },
      { full_name: '', fab_name: 'R3' },
      { full_name: 'SNAPSHOT/A', fab_name: 'r3' }
    ],
    recipe_names_complete: true,
    rows: [
      { full_name: 'SNAPSHOT/A', fab_name: 'R3' },
      { full_name: 'RAW/A', fab_name: 'R3' },
      { full_name: ' ', fab_name: 'R3' },
      { full_name: 'RAW/A', fab_name: 'R3' }
    ]
  }), {
    pairs: [pair('SNAPSHOT/A', 'R3'), pair('RAW/A', 'R3')],
    complete: false
  })
})

test('recipe-name snapshot accepts legacy bare-name entries with unknown fab', () => {
  // A stale office adapter still serves plain strings; the names must stay
  // usable (untagged) rather than poisoning the whole snapshot.
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: ['LEGACY/A', 'LEGACY/B'],
    recipe_names_complete: true,
    rows: []
  }), {
    pairs: [pair('LEGACY/A', ''), pair('LEGACY/B', '')],
    complete: true
  })
})

test('recipe-name snapshot preserves an intentionally empty complete array', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A', fab_name: 'R3' }]
  }), {
    pairs: [],
    complete: true
  })
})

test('recipe-name snapshot preserves fully valid pairs and uppercases fabs', () => {
  assert.deepEqual(normalizeRecipeNameSnapshot({
    recipe_names: [
      { full_name: 'SNAPSHOT/B', fab_name: 'm16b' },
      { full_name: 'SNAPSHOT/A', fab_name: 'R3' }
    ],
    recipe_names_complete: true,
    rows: [{ full_name: 'RAW/A', fab_name: 'R3' }]
  }), {
    pairs: [pair('SNAPSHOT/B', 'M16B'), pair('SNAPSHOT/A', 'R3')],
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
  const redis = toRecipeSearchResults(
    [{ recipe_name: 'A', fab_name: 'R3' }, { recipe_name: 'B', fab_name: 'R3' }],
    'redis'
  )
  const fallback = toRecipeSearchResults(
    [
      { recipe_name: 'B', fab_name: 'R3' },
      { recipe_name: 'C', fab_name: 'R3' },
      { recipe_name: 'C', fab_name: 'R3' }
    ],
    'opensearch'
  )
  assert.deepEqual(fallback, [
    { recipe_name: 'B', fab_name: 'R3', source: 'opensearch' },
    { recipe_name: 'C', fab_name: 'R3', source: 'opensearch' }
  ])
  assert.equal(activeRecipeResults(redis, fallback), redis)
  assert.equal(activeRecipeResults([], fallback), fallback)
})

test('toRecipeSearchResults keeps both fab copies of a duplicate name', () => {
  const rows = [
    { recipe_name: 'A/B_1', fab_name: 'R3' },
    { recipe_name: 'A/B_1', fab_name: 'M16B' },
    { recipe_name: 'A/B_1', fab_name: 'R3' }
  ]
  const results = toRecipeSearchResults(rows, 'redis')
  assert.deepEqual(results, [
    { recipe_name: 'A/B_1', fab_name: 'R3', source: 'redis' },
    { recipe_name: 'A/B_1', fab_name: 'M16B', source: 'redis' }
  ])
})

test('toRecipeSearchResults blank fab is allowed (opensearch fallback)', () => {
  const results = toRecipeSearchResults([{ recipe_name: 'X', fab_name: '' }], 'opensearch')
  assert.deepEqual(results, [{ recipe_name: 'X', fab_name: '', source: 'opensearch' }])
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

// ── registry check: the row's source stops being an inference ─────────────

const fallbackRow = (recipe: string, fab: string) =>
  ({ recipe_name: recipe, fab_name: fab, source: 'opensearch' as const })

test('confirmedRegistryPairs keeps only the confirmed pairs', () => {
  assert.deepEqual(confirmedRegistryPairs([
    { recipe_name: 'ADI/A', fab_name: 'R3', in_registry: true, reason: '' },
    { recipe_name: 'ADI/B', fab_name: 'R3', in_registry: false, reason: 'no entry' }
  ]), [{ recipe_name: 'ADI/A', fab_name: 'R3' }])
})

test('confirmed pairs promote a selection stored before the check answered', () => {
  // The row checkbox captures `source` at click time, so a row checked while
  // registry-check was in flight is persisted `opensearch`. One such entry
  // disables 열어보기 and 비교하기 for the WHOLE working set, so the confirmed
  // pairs have to reach the selection, not only the table.
  const stored = [{ name: 'ADI/A', fab_name: 'R3', source: 'opensearch' as const }]
  const confirmed = confirmedRegistryPairs([
    { recipe_name: 'ADI/A', fab_name: 'R3', in_registry: true, reason: '' }
  ])
  const promoted = promoteRecipeSelectionsToRedis(stored, confirmed)
  assert.equal(promoted[0]!.source, 'redis')
  assert.equal(capabilitiesForRecipeSelection(promoted).compare, true)
})

test('a declined pair leaves the selection alone', () => {
  const stored = [{ name: 'ADI/B', fab_name: 'R3', source: 'opensearch' as const }]
  const confirmed = confirmedRegistryPairs([
    { recipe_name: 'ADI/B', fab_name: 'R3', in_registry: false, reason: 'no entry' }
  ])
  assert.equal(promoteRecipeSelectionsToRedis(stored, confirmed), stored)
})

test('a confirmed fallback row is promoted to redis', () => {
  const rows = [fallbackRow('ADI/A', 'R3'), fallbackRow('ADI/B', 'R3')]
  const promoted = promoteVerifiedResults(rows, new Map([['R3|ADI/A', true]]))
  assert.deepEqual(promoted.map(row => row.source), ['redis', 'opensearch'])
})

test('promotion is per (recipe, fab) pair, never per name', () => {
  // The same name registered in R3 and absent from M16B is the normal case.
  const rows = [fallbackRow('ADI/A', 'R3'), fallbackRow('ADI/A', 'M16B')]
  const promoted = promoteVerifiedResults(rows, new Map([['R3|ADI/A', true]]))
  assert.deepEqual(promoted.map(row => [row.fab_name, row.source]), [
    ['R3', 'redis'],
    ['M16B', 'opensearch']
  ])
})

test('promotion never downgrades a redis row', () => {
  const rows = [{ recipe_name: 'ADI/A', fab_name: 'R3', source: 'redis' as const }]
  assert.equal(promoteVerifiedResults(rows, new Map()), rows)
  assert.equal(promoteVerifiedResults(rows, new Map([['R3|ADI/A', true]]))[0]!.source, 'redis')
})

test('promoting nothing returns the same array identity', () => {
  const rows = [fallbackRow('ADI/A', 'R3')]
  assert.equal(promoteVerifiedResults(rows, new Map()), rows)
  assert.equal(promoteVerifiedResults(rows, new Map([['R3|ADI/OTHER', true]])), rows)
})

test('a declined answer does not promote, and is distinct from unasked', () => {
  const rows = [fallbackRow('ADI/A', 'R3')]
  // false is the whole reason this is a map: it must read differently from an
  // absent key, which the caller retries.
  assert.equal(promoteVerifiedResults(rows, new Map([['R3|ADI/A', false]])), rows)
})
