// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { reconcileRecipeId } from './tttmRecipeScope.ts'

const MEASURED = ['CD_MONITOR/CD_MONITORING_HR_800V_X_FULL', 'CD_MONITOR/OTHER']

test('reconcileRecipeId: keeps a recipe the fab has measured', () => {
  assert.equal(reconcileRecipeId(MEASURED[0]!, MEASURED), MEASURED[0])
})

test('reconcileRecipeId: clears a recipe that is not in the measured list', () => {
  // The office regression this exists for: a recipeId persisted before the
  // picker was re-sourced from meas_hist names a CATALOGUE recipe nobody ran.
  // Driving it 502s the parameter fetch with
  //   "No document in meas_hist_cdsem has full_name=... for fab 'R3'".
  const stale = 'CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5'
  assert.equal(reconcileRecipeId(stale, MEASURED), null)
})

test('reconcileRecipeId: clears when the fab has measured nothing', () => {
  // An empty list is an ANSWER (this fab ran nothing), not an absent one — so
  // there is no recipe left that could be driven.
  assert.equal(reconcileRecipeId('anything', []), null)
})

test('reconcileRecipeId: keeps the pick while the list has not answered', () => {
  // null = still in flight, or the request failed. Clearing here would throw
  // away a working setup every time the catalogue request is slow or the
  // backend blips — the settings are persisted precisely so they survive that.
  assert.equal(reconcileRecipeId('CD_MONITOR/OTHER', null), 'CD_MONITOR/OTHER')
})

test('reconcileRecipeId: 전체 (no recipe) is never disturbed', () => {
  assert.equal(reconcileRecipeId(null, []), null)
  assert.equal(reconcileRecipeId(null, MEASURED), null)
  assert.equal(reconcileRecipeId(null, null), null)
})

test('reconcileRecipeId: matching is exact, not by bare recipe name', () => {
  // recipe_id IS the class/recipe full_name. A bare half that happens to be a
  // suffix of a measured full_name is a DIFFERENT identity — the office 502s
  // on it — so a substring match here would keep exactly the value that breaks.
  assert.equal(reconcileRecipeId('CD_MONITORING_HR_800V_X_FULL', MEASURED), null)
})
