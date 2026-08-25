// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analysisLock, offeredParameters, pickStillStands } from './tttmRecipeScope.ts'

const MEASURED = ['CD_MONITOR/CD_MONITORING_HR_800V_X_FULL', 'CD_MONITOR/OTHER']

test('pickStillStands (recipe): a recipe the fab has measured stands', () => {
  assert.equal(pickStillStands(MEASURED[0]!, MEASURED), true)
})

test('pickStillStands (recipe): a recipe that is not in the measured list does not', () => {
  // The office regression this exists for: a recipeId persisted before the
  // picker was re-sourced from meas_hist names a CATALOGUE recipe nobody ran.
  // Driving it 502s the parameter fetch with
  //   "No document in meas_hist_cdsem has full_name=... for fab 'R3'".
  const stale = 'CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5'
  assert.equal(pickStillStands(stale, MEASURED), false)
})

test('pickStillStands (recipe): nothing stands when the fab has measured nothing', () => {
  // An empty list is an ANSWER (this fab ran nothing), not an absent one — so
  // there is no recipe left that could be driven.
  assert.equal(pickStillStands('anything', []), false)
})

test('pickStillStands (recipe): the pick stands while the list has not answered', () => {
  // null = still in flight, or the request failed. Clearing here would throw
  // away a working setup every time the catalogue request is slow or the
  // backend blips — the settings are persisted precisely so they survive that.
  assert.equal(pickStillStands('CD_MONITOR/OTHER', null), true)
})

test('pickStillStands (recipe): 전체 (no recipe) always stands', () => {
  // Never disturbed, in any of the three list states — there is no pick to go
  // stale, and clearing what is already cleared would rewrite storage on every
  // catalogue answer.
  assert.equal(pickStillStands(null, []), true)
  assert.equal(pickStillStands(null, MEASURED), true)
  assert.equal(pickStillStands(null, null), true)
})

test('pickStillStands (recipe): matching is exact, not by bare recipe name', () => {
  // recipe_id IS the class/recipe full_name. A bare half that happens to be a
  // suffix of a measured full_name is a DIFFERENT identity — the office 502s
  // on it — so a substring match here would keep exactly the value that breaks.
  assert.equal(pickStillStands('CD_MONITORING_HR_800V_X_FULL', MEASURED), false)
})

// ── the parameter half ────────────────────────────────────────────────────

const answered = (recipe_id: string | null, parameters: string[], available = true) =>
  ({ available, recipe_id, parameters })

test('offeredParameters: the payload of the picked recipe is the answer', () => {
  assert.deepEqual(
    offeredParameters(answered('CD_MONITOR/OTHER', ['CD_X', 'CD_Y']), 'CD_MONITOR/OTHER'),
    ['CD_X', 'CD_Y']
  )
})

test('offeredParameters: an empty list from the picked recipe is still an answer', () => {
  // "This recipe measured nothing named" clears a stale pick; it is not the
  // absence of an answer.
  assert.deepEqual(offeredParameters(answered('CD_MONITOR/OTHER', []), 'CD_MONITOR/OTHER'), [])
})

test('offeredParameters: no payload yet is no answer', () => {
  assert.equal(offeredParameters(null, 'CD_MONITOR/OTHER'), null)
  assert.equal(offeredParameters(undefined, 'CD_MONITOR/OTHER'), null)
})

test('offeredParameters: a payload still answering the PREVIOUS recipe is no answer', () => {
  // useAsyncData keeps the old data while the next request is in flight, so
  // the list on screen can belong to a recipe the user has already left.
  assert.equal(offeredParameters(answered('CD_MONITOR/OTHER', ['CD_X']), MEASURED[0]!), null)
})

test('offeredParameters: an unavailable payload is no answer', () => {
  // An unavailable branch carries `parameters: []` by contract, and reading
  // that as "the recipe has no parameters" would erase a working pick on a
  // window with no runs.
  assert.equal(offeredParameters(answered('CD_MONITOR/OTHER', [], false), 'CD_MONITOR/OTHER'), null)
})

test('offeredParameters: without a recipe there is nothing to offer', () => {
  assert.equal(offeredParameters(answered(null, []), null), null)
})

test('pickStillStands: a parameter the recipe did not measure is dropped', () => {
  // The same law as the recipe: a persisted "Para_13" outliving an .idp
  // revision names nothing, and the office would answer an empty grid that
  // blames the recipe.
  assert.equal(pickStillStands('Para_13', ['CD_X', 'CD_Y']), false)
  assert.equal(pickStillStands('CD_X', ['CD_X', 'CD_Y']), true)
  assert.equal(pickStillStands('Para_13', null), true)
  assert.equal(pickStillStands(null, []), true)
})

// ── the lock on the 분석 조건 bar ─────────────────────────────────────────

test('analysisLock: no recipe is the first step missing, whatever else is true', () => {
  assert.equal(analysisLock(null, true, null), 'no-recipe')
})

test('analysisLock: an unavailable answer locks for a reason, not for a moment', () => {
  // offeredParameters reads an unavailable payload as "no answer", and with
  // nothing in flight that is the recipe's verdict.
  assert.equal(analysisLock('R', false, offeredParameters(answered('R', [], false), 'R')), 'no-data')
})

test('analysisLock: a failed request is no-data, not a live picker over nothing', () => {
  // payload null, nothing pending: the picker must not enable over an empty
  // list and claim the recipe measured no named parameter.
  assert.equal(analysisLock('R', false, null), 'no-data')
})

test('analysisLock: no answer yet while the request is in flight is loading', () => {
  assert.equal(analysisLock('R', true, null), 'loading')
  // A payload still answering the PREVIOUS recipe — available or not — reads
  // the same way; its verdict is not this recipe's.
  assert.equal(analysisLock('R', true, offeredParameters(answered('OTHER', [], false), 'R')), 'loading')
})

test('analysisLock: an answer for the picked recipe is live, even mid-refetch', () => {
  // The parameter filter re-requests the payload; the stale-but-available
  // list keeps the controls usable while that is in flight.
  assert.equal(analysisLock('R', true, ['CD_X']), null)
  assert.equal(analysisLock('R', false, []), null)
})
