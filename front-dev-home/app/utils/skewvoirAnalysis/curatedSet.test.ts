import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TREND_LIMIT, resolveSetRows, shouldLoadSet } from './curatedSet.ts'

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
