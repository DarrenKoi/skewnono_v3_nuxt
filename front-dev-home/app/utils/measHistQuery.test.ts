// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseMeasHistQuery, removeToken } from './measHistQuery.ts'

const KNOWN = {
  eq: ['ECXDX925', 'ECDX753', 'MCD018'],
  recipe: ['CNT/CNT_CONTACT_CHECK_ABC123_QUAL_00008', 'ADI/ADI_CD_BIAS_001', 'DEF/DEF_REVIEW_001']
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

test('recipe matches full_name, bare recipe_name, and case-insensitive substring', () => {
  assert.deepEqual(parseMeasHistQuery('ADI/ADI_CD_BIAS_001', KNOWN).recipe, ['ADI/ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('ADI_CD_BIAS_001', KNOWN).recipe, ['ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('cd_bias', KNOWN).recipe, ['cd_bias'])
})

test('a token matching nothing is unknown', () => {
  const r = parseMeasHistQuery('zzz', KNOWN)
  assert.deepEqual(r.unknown, ['zzz'])
  assert.deepEqual(r.recipe, [])
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
