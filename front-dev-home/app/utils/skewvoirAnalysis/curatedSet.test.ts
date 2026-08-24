import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TREND_LIMIT, isSetColdLoading, isSetCompatibilityKnown, isSetPoolComplete, rendersFocusAlone, resolveSetRows, shouldLoadSet } from './curatedSet.ts'

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

test('rendersFocusAlone: the two views that draw ONE measurement under a set', () => {
  assert.equal(rendersFocusAlone('dashboard'), true)
  // The gallery's set-scope branch is a grid of the FOCUS measurement's image
  // files, so it needs the picker just as much as the dashboard does. It was
  // the view this rule got wrong when it was spelled `=== 'dashboard'`.
  assert.equal(rendersFocusAlone('gallery'), true)
})

test('rendersFocusAlone: the views that draw the whole set at once', () => {
  assert.equal(rendersFocusAlone('position-stack'), false)
  assert.equal(rendersFocusAlone('time-series'), false)
  assert.equal(rendersFocusAlone('correlation'), false)
  assert.equal(rendersFocusAlone('fdc'), false)
})

test('rendersFocusAlone is NOT the negation of shouldLoadSet — they disagree on the gallery', () => {
  // Focus-only AND still batch-fetched: manifest.counts feeds the rail in every
  // view. Deriving either rule from the other would starve one of them.
  assert.equal(rendersFocusAlone('gallery'), true)
  assert.equal(shouldLoadSet('set', 'gallery'), true)
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

// --- isSetColdLoading: is the set-scope view still waiting with nothing to draw? ---

const COLD = { wantSet: true, loaded: 0, historyPending: true, filesPending: false }

test('isSetColdLoading: the meas_hist round-trip counts as loading, before any set key exists', () => {
  // The half `setPending` cannot see: no history means no resolved set rows,
  // so no key, so no batch — and the views would otherwise render their empty
  // states as if the answer were "your set is empty".
  assert.equal(isSetColdLoading(COLD), true)
})

test('isSetColdLoading: the msr_file batch counts as loading too', () => {
  assert.equal(isSetColdLoading({ ...COLD, historyPending: false, filesPending: true }), true)
})

test('isSetColdLoading: a warm set edit is NOT cold — the carried files stay on screen', () => {
  // An add/remove over a loaded set keeps the previous files, so the charts
  // remain rendered and the in-panel inline spinner owns that feedback.
  assert.equal(isSetColdLoading({ ...COLD, loaded: 3, historyPending: false, filesPending: true }), false)
})

test('isSetColdLoading: nothing in flight is not loading, however empty the set', () => {
  // A set that genuinely resolves to nothing must reach its real empty state
  // rather than spin forever.
  assert.equal(isSetColdLoading({ ...COLD, historyPending: false, filesPending: false }), false)
})

test('isSetColdLoading: a view that does not want the set never shows the loader', () => {
  // Dashboard and single scope run off the focus file, which has its own
  // pending flag — a set fetch they never asked for must not block them.
  assert.equal(isSetColdLoading({ ...COLD, wantSet: false }), false)
})

// --- isSetCompatibilityKnown: is the rail's 호환 chip an answer or an artefact? ---

test('isSetCompatibilityKnown: a set with no files loaded has nothing to count', () => {
  // The focus loads on its own path, so the manifest compares it against
  // itself and reports 호환 1 beside a 9-member list.
  assert.equal(isSetCompatibilityKnown({ members: 9, loaded: 0 }), false)
})

test('isSetCompatibilityKnown: one loaded file is enough to state a real count', () => {
  // Partial or stale, but computed over files — and a warm set edit keeps the
  // previous ones, so the chip holds its last answer rather than blinking.
  assert.equal(isSetCompatibilityKnown({ members: 9, loaded: 8 }), true)
})

test('isSetCompatibilityKnown: a single measurement is always known', () => {
  // 호환 1 is the whole truth for a set of one, not a floor, so the Dashboard
  // under single scope keeps its number.
  assert.equal(isSetCompatibilityKnown({ members: 1, loaded: 0 }), true)
})
