// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseMeasHistQuery, removeToken, resolveDateRange, stripDateTokens } from './measHistQuery.ts'

// No `recipe` list: there is no RECIPE facet/dropdown (removed — the office
// index carries hundreds of recipes). A token unmatched by every other rule
// falls through to cross-field `q`, which searches every searchable field.
const KNOWN = {
  eq: ['ECXDX925', 'ECDX753', 'MCD018']
}

const EMPTY = { eq: [], lot: [], recipe: [], msr: [], date: [], q: [], unknown: [] }

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
  // Same prefix, not a faceted exact id -> robust cross-field fallback.
  const fallback = parseMeasHistQuery('ECXDX999', KNOWN)
  assert.deepEqual(fallback.eq, [])
  assert.deepEqual(fallback.q, ['ECXDX999'])
})

test('lot id shape is detected', () => {
  assert.deepEqual(parseMeasHistQuery('6LD257421', KNOWN).lot, ['6LD257421'])
  assert.deepEqual(parseMeasHistQuery('RKPB240012', KNOWN).lot, ['RKPB240012'])
})

// Fix 2: code (`\d{6}`) contradicted spec §4.2 (`\d{6,8}`). All 600 mock lots
// happen to have exactly 6-digit tails, so nothing failed locally — but the
// office index is not guaranteed to. A 7-8 digit lot id must classify as
// `lot`, not fall through to `recipe` (green chip, honest-looking zero rows
// that are actually a misread lot id).
test('lot id shape accepts 7 and 8 digit tails per spec §4.2, not just 6', () => {
  assert.deepEqual(parseMeasHistQuery('6LD2574210', KNOWN).lot, ['6LD2574210'])
  assert.deepEqual(parseMeasHistQuery('RKPB24001234', KNOWN).lot, ['RKPB24001234'])
})

// Widening the digit tail must not start swallowing real eq ids. Eq ids top
// out at 8 total characters (a 3-5 char prefix + 3 digits — see
// back_dev_home/sem_list/providers/mock.py), below the lot pattern's 9-char
// floor (3 alnum + 6 digits), so no known eq id shape can collide.
test('widened lot regex does not swallow a known eq id', () => {
  const r = parseMeasHistQuery('ECXDX925', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925'])
  assert.deepEqual(r.lot, [])
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

// Fix 1: a digit-shape match alone is not enough — 2026-13-45, 2026-02-30 and
// 99999999 all match the DASHED/COMPACT shape but are not real calendar
// dates. Classifying them as `date` sends an unparseable from/to bound to
// the backend, which (pre-fix) silently widened the query to the entire
// 60-day retention window instead of returning honest zero rows. A bare
// invalid-date token must fall through every other shape rule to the
// cross-field fallback (honest zero rows), never `date`.
test('an invalid calendar date is not classified as date, even though its digit shape matches', () => {
  const impossibleMonth = parseMeasHistQuery('2026-13-45', KNOWN)
  assert.deepEqual(impossibleMonth.date, [])
  assert.deepEqual(impossibleMonth.q, ['2026-13-45'])

  const impossibleDay = parseMeasHistQuery('2026-02-30', KNOWN)
  assert.deepEqual(impossibleDay.date, [])
  assert.deepEqual(impossibleDay.q, ['2026-02-30'])

  const impossibleCompact = parseMeasHistQuery('99999999', KNOWN)
  assert.deepEqual(impossibleCompact.date, [])
  assert.deepEqual(impossibleCompact.q, ['99999999'])
})

// Fix 1: the PREFIXED form of the same bad dates must land in `unknown` (red
// chip) instead — the user explicitly forced the `date:` field, so a shape
// that fails calendar validation is a malformed prefix, not a recipe guess.
test('an invalid calendar date behind a date: prefix is unknown, not date or recipe', () => {
  const r = parseMeasHistQuery('date:2026-13-45', KNOWN)
  assert.deepEqual(r.unknown, ['2026-13-45'])
  assert.deepEqual(r.date, [])
  assert.deepEqual(r.recipe, [])
})

test('unprefixed recipe names and fragments use cross-field fallback', () => {
  assert.deepEqual(parseMeasHistQuery('ADI/ADI_CD_BIAS_001', KNOWN).q, ['ADI/ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('ADI_CD_BIAS_001', KNOWN).q, ['ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('cd_bias', KNOWN).q, ['cd_bias'])
})

test('an otherwise-unclassified token becomes a cross-field fallback, not unknown', () => {
  const r = parseMeasHistQuery('zzz', KNOWN)
  assert.deepEqual(r.q, ['zzz'])
  assert.deepEqual(r.recipe, [])
  assert.deepEqual(r.unknown, [])
})

test('an equipment prefix uses cross-field fallback so ECXDX finds ECXDX925', () => {
  const r = parseMeasHistQuery('ECXDX', KNOWN)
  assert.deepEqual(r.eq, [])
  assert.deepEqual(r.q, ['ECXDX'])
})

test('field: prefix overrides shape rules', () => {
  // Looks like a lot, forced to recipe.
  assert.deepEqual(parseMeasHistQuery('recipe:6LD257421', KNOWN).recipe, ['6LD257421'])
  // Not a known eq, forced to eq.
  assert.deepEqual(parseMeasHistQuery('eq:ECXDX999', KNOWN).eq, ['ECXDX999'])
  assert.deepEqual(parseMeasHistQuery('lot:zzz', KNOWN).lot, ['zzz'])
  assert.deepEqual(parseMeasHistQuery('msr:abc', KNOWN).msr, ['abc'])
  assert.deepEqual(parseMeasHistQuery('q:ECXDX', KNOWN).q, ['ECXDX'])
  assert.deepEqual(parseMeasHistQuery('date:20260510', KNOWN).date, ['2026-05-10'])
})

// With the recipe facet gone, classify()'s only remaining route to `unknown`
// is a malformed `field:` prefix — a plain unmatched token now falls to
// `q` instead (see the test above). Pin that `unknown` still exists for
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

test('without facets, shape rules still work and leftovers become cross-field terms', () => {
  const r = parseMeasHistQuery('ECXDX925 6LD257421 2026-05-10')
  assert.deepEqual(r.lot, ['6LD257421'])
  assert.deepEqual(r.date, ['2026-05-10'])
  assert.deepEqual(r.q, ['ECXDX925'])
  assert.deepEqual(r.recipe, [])
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
// THEN writes filters.from/to, so resolveDateRange has nothing left to prefer
// over the dropdown's pick.
//
// Fix 3: the previous version of this test re-implemented that strip step
// inline with `removeToken`, calling a helper the composable doesn't call —
// it exercised removeToken/resolveDateRange, not the actual code path, and
// would keep passing even if the strip step were deleted from setDateRange.
// `stripDateTokens` is the exact pure helper useMeasHistSearch.ts's
// setDateRange calls (see its import there), so testing it here tests real
// production code, not a stand-in. Delete the `.reduce` body inside
// stripDateTokens and this test fails — that's what "not vacuous" means.
test('stripDateTokens removes every parsed date token, leaving other tokens and separators intact', () => {
  const queryText = 'MCD018 date:2026-05-05 6LD257421'
  const parsed = parseMeasHistQuery(queryText, KNOWN)
  assert.deepEqual(parsed.date, ['2026-05-05'])

  const stripped = stripDateTokens(queryText, parsed.date)
  assert.equal(stripped, 'MCD018 6LD257421')
  assert.equal(stripped.includes('2026-05-05'), false)

  // With the date token gone, a re-parse of the stripped text has nothing
  // left to out-rank the dropdown's freshly-picked range.
  const reparsed = parseMeasHistQuery(stripped, KNOWN)
  const filterFrom = '2026-05-01'
  const filterTo = '2026-05-08'
  assert.deepEqual(
    resolveDateRange(reparsed.date, filterFrom, filterTo, '2026-03-11', '2026-05-10'),
    { start: filterFrom, end: filterTo }
  )
})

test('stripDateTokens is a no-op when there are no date tokens to strip', () => {
  assert.equal(stripDateTokens('MCD018 6LD257421', []), 'MCD018 6LD257421')
})
