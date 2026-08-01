import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TREND_LIMIT, isSetPoolComplete, resolveSetRows, shouldLoadSet } from './curatedSet.ts'

interface MeasHistRowFixture { msr: string, msr_check: 'Yes' | 'No' }

test('resolveSetRows preserves the authored msrs order (not sorted), dropping missing msrs', () => {
  const rowByMsr = new Map<string, MeasHistRowFixture>([
    ['msr-c', { msr: 'msr-c', msr_check: 'Yes' }],
    ['msr-a', { msr: 'msr-a', msr_check: 'Yes' }]
    // 'msr-b' intentionally absent — simulates a missing/unresolvable msr id
  ])
  const result = resolveSetRows(['msr-a', 'msr-b', 'msr-c'], rowByMsr)
  assert.deepEqual(result.map(r => r.msr), ['msr-a', 'msr-c'])
})

test('resolveSetRows caps the curated set at TREND_LIMIT (30), keeping the leading msrs entries', () => {
  const ids = Array.from({ length: 40 }, (_, i) => `msr-${i}`)
  const rowByMsr = new Map(ids.map(id => [id, { msr: id, msr_check: 'Yes' as const }]))
  const result = resolveSetRows(ids, rowByMsr)
  assert.equal(result.length, TREND_LIMIT)
  assert.deepEqual(result.map(r => r.msr), ids.slice(0, TREND_LIMIT))
})

test('shouldLoadSet: under set scope, every non-dashboard detail view triggers the curated-set batch fetch', () => {
  assert.equal(shouldLoadSet('set', 'position-stack'), true)
  assert.equal(shouldLoadSet('set', 'time-series'), true)
  assert.equal(shouldLoadSet('set', 'correlation'), true)
  assert.equal(shouldLoadSet('set', 'gallery'), true)
  // fdc renders only its empty state under set scope (its single-scope
  // content is the sequence workbench), but manifest.counts still feeds the
  // left rail there, so the batch fetch must still fire.
  assert.equal(shouldLoadSet('set', 'fdc'), true)
})

test('shouldLoadSet lazy-load invariant: Dashboard NEVER triggers the batch fetch, even under set scope', () => {
  assert.equal(shouldLoadSet('set', 'dashboard'), false)
  assert.equal(shouldLoadSet('single', 'dashboard'), false)
})

test('shouldLoadSet: under single scope no view triggers the batch fetch (no comparison set to load)', () => {
  assert.equal(shouldLoadSet('single', 'time-series'), false)
  assert.equal(shouldLoadSet('single', 'position-stack'), false)
  assert.equal(shouldLoadSet('single', 'correlation'), false)
  assert.equal(shouldLoadSet('single', 'gallery'), false)
})

// --- isSetPoolComplete: does the loaded set answer the set we are asking about? ---
// Feeds activeParamPool's `setComplete`. Lives here as a pure rule because the
// composable that used to hold it inline has no test harness, and this is the
// predicate that decides whether the URL may be rewritten.

const COMPLETE = { pending: false, loadedKey: 'a|b', wantedKey: 'a|b', loaded: 2, expected: 2 }

test('isSetPoolComplete: a settled, fully loaded set for the current key is complete', () => {
  assert.equal(isSetPoolComplete(COMPLETE), true)
})

test('isSetPoolComplete: a batch still in flight is not complete', () => {
  // setFiles still holds the PREVIOUS set while the new one is fetching.
  assert.equal(isSetPoolComplete({ ...COMPLETE, pending: true }), false)
})

test('isSetPoolComplete: a part-loaded set is not complete', () => {
  // /api/msr-files returns found MSRs only and silently skips the rest.
  assert.equal(isSetPoolComplete({ ...COMPLETE, loaded: 1 }), false)
})

test('isSetPoolComplete: files belonging to a DIFFERENT set are not complete', () => {
  // A failed batch leaves the previous set's map in place. Same size is not
  // the same set — two 5-msr sets would otherwise look interchangeable.
  assert.equal(isSetPoolComplete({ ...COMPLETE, loadedKey: 'c|d' }), false)
})

test('isSetPoolComplete: an empty set on an empty key is vacuously complete', () => {
  // Non-set scope clears both. activeParamPool still refuses to widen (no set
  // params), so this never grants authority the set itself has not earned.
  assert.equal(isSetPoolComplete({
    pending: false, loadedKey: '', wantedKey: '', loaded: 0, expected: 0
  }), true)
})
