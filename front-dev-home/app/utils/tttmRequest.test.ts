// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { checkIsStale, rosterFromSemList } from './tttmRequest.ts'

const echo = (over: Partial<Parameters<typeof checkIsStale>[0] & object> = {}) => ({
  recipe_id: 'CD_MONITOR/R',
  selected_parameters: ['P1', 'P2'],
  window_weeks: 2,
  tools: [{ eqp_id: 'A' }, { eqp_id: 'B' }],
  ...over
})
const scope = {
  recipeId: 'CD_MONITOR/R',
  parameters: ['P2', 'P1'],
  windowWeeks: 2,
  tools: ['B', 'A']
}

test('checkIsStale: no payload is stale — there is nothing to draw', () => {
  assert.equal(checkIsStale(null, scope), true)
  assert.equal(checkIsStale(undefined, scope), true)
})

test('checkIsStale: the same scope in another order is NOT stale', () => {
  // The picker orders by fleet, the server echoes roster order, and the
  // parameter set is a set — none of that is a change the user made.
  assert.equal(checkIsStale(echo(), scope), false)
})

test('checkIsStale: each axis of the scope can go stale on its own', () => {
  assert.equal(checkIsStale(echo({ recipe_id: 'OTHER' }), scope), true)
  assert.equal(checkIsStale(echo({ window_weeks: 3 }), scope), true)
  assert.equal(checkIsStale(echo({ selected_parameters: ['P1'] }), scope), true)
  assert.equal(checkIsStale(echo({ tools: [{ eqp_id: 'A' }] }), scope), true)
  // A tool ADDED to the selection is stale too: the server never gathered it.
  assert.equal(checkIsStale(echo(), { ...scope, tools: ['A', 'B', 'C'] }), true)
})

test('checkIsStale: an unavailable answer for the same scope is fresh', () => {
  // The server echoes the narrowed roster even on available:false, so "no
  // data for these two" is an answer to the question, not a stale one.
  assert.equal(checkIsStale(echo({ selected_parameters: [] }), { ...scope, parameters: [] }), false)
})

test('rosterFromSemList: dedupes by eqp_id and sorts — the sem_list/roster.py law', () => {
  const roster = rosterFromSemList([
    { eqp_id: 'CG2', eqp_model_cd: 'CG6300' },
    { eqp_id: 'CG1', eqp_model_cd: 'CG6300' },
    // sem_list's mock really does repeat ids (~10 of 300 rows).
    { eqp_id: 'CG2', eqp_model_cd: 'CG6300' }
  ])
  assert.deepEqual(roster.map(t => t.eqp_id), ['CG1', 'CG2'])
  assert.deepEqual(roster[0], { eqp_id: 'CG1', label: 'CG1', eqp_model_cd: 'CG6300' })
})
