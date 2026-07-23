import { test } from 'node:test'
import assert from 'node:assert/strict'
import { matchesRecipeQuery, matchingHistoryNames, tokenizeRecipeQuery } from './recipeSearchMatch.ts'

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
