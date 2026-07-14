// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseMeasHistQuery, removeToken, resolveDateRange } from './measHistQuery.ts'

// No `recipe` list: there is no RECIPE facet/dropdown (removed — the office
// index carries hundreds of recipes). A token unmatched by every other rule
// falls through to `recipe` regardless of what's "known" — see classify()'s
// terminal branch in measHistQuery.ts.
const KNOWN = {
  eq: ['ECXDX925', 'ECDX753', 'MCD018']
}

const EMPTY = { eq: [], lot: [], recipe: [], msr: [], date: [], unknown: [] }

test('empty input parses to all-empty', () => {
  assert.deepEqual(parseMeasHistQuery('', KNOWN), EMPTY)
  assert.deepEqual(parseMeasHistQuery('   ', KNOWN), EMPTY)
})

test('splits on whitespace, comma and semicolon alike', () => {
  const r = parseMeasHistQuery('ECXDX925, ECDX753; MCD018', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'ECDX753', 'MCD018'])
})

test('tolerates repeated and trailing separators', () => {
  const r = parseMeasHistQuery('ECXDX925 ,,  ECDX753 ;', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'ECDX753'])
  assert.deepEqual(r.unknown, [])
})

test('known equipment id is detected exactly, not by prefix guessing', () => {
  assert.deepEqual(parseMeasHistQuery('ECXDX925', KNOWN).eq, ['ECXDX925'])
  // Same prefix, not a real tool -> not an eq.
  assert.deepEqual(parseMeasHistQuery('ECXDX999', KNOWN).eq, [])
})

test('lot id shape is detected', () => {
  assert.deepEqual(parseMeasHistQuery('6LD257421', KNOWN).lot, ['6LD257421'])
  assert.deepEqual(parseMeasHistQuery('RKPB240012', KNOWN).lot, ['RKPB240012'])
})

test('msr is detected by its leading 8-digit date, despite underscores in the recipe', () => {
  const msr = '20260315_CNT_CONTACT_CHECK_ABC123_QUAL_00008_6LD257421_ECXDX925'
  const r = parseMeasHistQuery(msr, KNOWN)
  assert.deepEqual(r.msr, [msr])
  assert.deepEqual(r.date, [])
  assert.deepEqual(r.lot, [])
})

test('both date forms normalize to YYYY-MM-DD', () => {
  assert.deepEqual(parseMeasHistQuery('2026-05-10', KNOWN).date, ['2026-05-10'])
  assert.deepEqual(parseMeasHistQuery('20260510', KNOWN).date, ['2026-05-10'])
})

test('a full_name, a bare recipe_name, and a bare fragment all classify as recipe (no facet to check against)', () => {
  assert.deepEqual(parseMeasHistQuery('ADI/ADI_CD_BIAS_001', KNOWN).recipe, ['ADI/ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('ADI_CD_BIAS_001', KNOWN).recipe, ['ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('cd_bias', KNOWN).recipe, ['cd_bias'])
})

// Was: "a token matching nothing is unknown". There is no recipe facet to
// confirm a match against anymore, so the terminal fallback in classify()
// is `recipe`, not `unknown` — a bogus recipe now returns zero rows
// honestly instead of being dropped from the request and silently widening
// the query to everything (see classify()'s terminal-branch comment).
test('an otherwise-unclassified token is treated as a recipe substring, not dropped as unknown', () => {
  const r = parseMeasHistQuery('zzz', KNOWN)
  assert.deepEqual(r.recipe, ['zzz'])
  assert.deepEqual(r.unknown, [])
})

test('field: prefix overrides shape rules', () => {
  // Looks like a lot, forced to recipe.
  assert.deepEqual(parseMeasHistQuery('recipe:6LD257421', KNOWN).recipe, ['6LD257421'])
  // Not a known eq, forced to eq.
  assert.deepEqual(parseMeasHistQuery('eq:ECXDX999', KNOWN).eq, ['ECXDX999'])
  assert.deepEqual(parseMeasHistQuery('lot:zzz', KNOWN).lot, ['zzz'])
  assert.deepEqual(parseMeasHistQuery('msr:abc', KNOWN).msr, ['abc'])
  assert.deepEqual(parseMeasHistQuery('date:20260510', KNOWN).date, ['2026-05-10'])
})

// With the recipe facet gone, classify()'s only remaining route to `unknown`
// is a malformed `field:` prefix — a plain unmatched token now falls to
// `recipe` instead (see the test above). Pin that `unknown` still exists for
// this one case, so the red `?` chip has something real to render.
test('unknown is reserved for a malformed field: prefix, e.g. an unparseable date', () => {
  const r = parseMeasHistQuery('date:notadate', KNOWN)
  assert.deepEqual(r.unknown, ['notadate'])
  assert.deepEqual(r.date, [])
  assert.deepEqual(r.recipe, [])
})

test('field: prefix is case-insensitive and empty values are ignored', () => {
  assert.deepEqual(parseMeasHistQuery('LOT:6LD257421', KNOWN).lot, ['6LD257421'])
  assert.deepEqual(parseMeasHistQuery('lot:', KNOWN), EMPTY)
})

test('same field accumulates, different fields coexist', () => {
  const r = parseMeasHistQuery('ECXDX925 MCD018 6LD257421 2026-05-10', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'MCD018'])
  assert.deepEqual(r.lot, ['6LD257421'])
  assert.deepEqual(r.date, ['2026-05-10'])
})

test('duplicate tokens are de-duplicated', () => {
  assert.deepEqual(parseMeasHistQuery('MCD018 MCD018', KNOWN).eq, ['MCD018'])
})

test('without facets, shape rules still work and leftovers become recipe substrings', () => {
  const r = parseMeasHistQuery('ECXDX925 6LD257421 2026-05-10')
  assert.deepEqual(r.lot, ['6LD257421'])
  assert.deepEqual(r.date, ['2026-05-10'])
  // No known list to confirm against, so it stays a recipe guess rather than unknown.
  assert.deepEqual(r.recipe, ['ECXDX925'])
  assert.deepEqual(r.unknown, [])
})

test('removeToken drops only that token and leaves the rest usable', () => {
  assert.equal(removeToken('ECXDX925, MCD018 ; 6LD257421', 'MCD018'), 'ECXDX925 6LD257421')
  assert.equal(removeToken('lot:6LD257421 MCD018', '6LD257421'), 'MCD018')
  assert.equal(removeToken('MCD018', 'MCD018'), '')
})

// Fix 3: the × on a compact-date chip passes the NORMALIZED value
// ('2026-05-10'), but the raw text still holds the compact/prefixed form
// the user typed. removeToken must match through normalizeDate, not just a
// literal string compare, or the × silently does nothing.
test('removeToken matches a compact-date token via its normalized value', () => {
  assert.equal(removeToken('20260510 MCD018', '2026-05-10'), 'MCD018')
  assert.equal(removeToken('date:20260510 MCD018', '2026-05-10'), 'MCD018')
})

// Fix 2: the backend upper-cases both sides of the eq compare, so a
// lowercase-typed known eq id must classify as 'eq', not fall through to
// 'unknown' and get silently dropped from the request.
test('a lowercase known-eq token classifies as eq, not unknown', () => {
  const r = parseMeasHistQuery('ecdx753', KNOWN)
  assert.deepEqual(r.eq, ['ecdx753'])
  assert.deepEqual(r.unknown, [])
})

// Fix 1 / spec §6.3: a typed `date:` token must win over whatever the 기간
// dropdown already holds, and the resolved range is what both the request
// AND the displayed 기간 chip must use — one source of truth, not two.
test('resolveDateRange: a date token wins over the dropdown; the dropdown wins over the default', () => {
  // No date token: dropdown filter values apply.
  assert.deepEqual(
    resolveDateRange([], '2026-04-01', '2026-04-30', '2026-03-11', '2026-05-10'),
    { start: '2026-04-01', end: '2026-04-30' }
  )
  // A single date token overrides the dropdown entirely, even though the
  // dropdown still holds a (now stale) value.
  assert.deepEqual(
    resolveDateRange(['2026-05-09'], '2026-04-01', '2026-04-30', '2026-03-11', '2026-05-10'),
    { start: '2026-05-09', end: '2026-05-09' }
  )
  // Two date tokens form a range, unsorted input included, still overriding
  // the dropdown.
  assert.deepEqual(
    resolveDateRange(['2026-05-09', '2026-05-01'], '2026-04-01', '2026-04-30', '2026-03-11', '2026-05-10'),
    { start: '2026-05-01', end: '2026-05-09' }
  )
  // Neither a token nor a dropdown value: falls back to the default range.
  assert.deepEqual(
    resolveDateRange([], '', '', '2026-03-11', '2026-05-10'),
    { start: '2026-03-11', end: '2026-05-10' }
  )
})

// Blocking review finding: EbeamDateRangePopover is fully controlled by
// resolvedRange, so while a `date:` token sits in queryText, picking a range
// in the dropdown used to only ever write filters.from/to — resolvedRange
// stayed derived from the (unchanged) token, so the popover label snapped
// right back to it, and hasActiveFilters lit up 초기화 for a date the query
// silently ignored. useMeasHistSearch's setDateRange fixes this by making a
// dropdown edit "last write wins": it strips the date token out of queryText
// (via removeToken, which already handles bare/normalized/prefixed forms)
// THEN writes filters.from/to, so resolveDateRange has nothing left to prefer
// over the dropdown's pick. This test pins that exact sequence — the same two
// pure functions setDateRange composes — without needing Vue's reactivity
// runtime (this repo's tests are plain `node --test`, no Nuxt/Vue test infra;
// see the file header).
test('setDateRange contract: stripping the date token before resolving makes the dropdown pick win, not the stale token', () => {
  let queryText = 'MCD018 date:2026-05-05'
  const parsed = parseMeasHistQuery(queryText, KNOWN)
  assert.deepEqual(parsed.date, ['2026-05-05'])

  // setDateRange's first step: strip every parsed date token out of queryText.
  for (const token of parsed.date) {
    queryText = removeToken(queryText, token)
  }
  assert.equal(queryText, 'MCD018')
  assert.equal(queryText.includes('2026-05-05'), false)

  // setDateRange's second step: filters.from/to become the dropdown's range.
  const filterFrom = '2026-05-01'
  const filterTo = '2026-05-08'

  // resolvedRange is recomputed against the now-stripped query text, so the
  // stale date token can no longer win over the freshly-picked range.
  const reparsed = parseMeasHistQuery(queryText, KNOWN)
  assert.deepEqual(
    resolveDateRange(reparsed.date, filterFrom, filterTo, '2026-03-11', '2026-05-10'),
    { start: filterFrom, end: filterTo }
  )
})
