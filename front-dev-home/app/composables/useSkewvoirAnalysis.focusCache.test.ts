import { test } from 'node:test'
import assert from 'node:assert/strict'

// CHARACTERIZATION TESTS — see currentContracts.test.ts for why: the Nuxt
// runtime (useState, useAsyncData, computed, watch, …) is undefined under the
// raw `node --test` harness this repo runs, so useSkewvoirAnalysis.ts cannot
// be imported and driven directly here. Each test below mirrors ONE rule of
// Task 3b's focus-file session cache as a small local pure function, cited by
// exact source file:line, and asserted against fixtures.
//
// Task 3b — overview focus-switcher chip strip. Rules mirrored:
//   • TREND_LIMIT (useSkewvoirAnalysis.ts:14) bounds the cache size.
//   • cacheFocusFile (useSkewvoirAnalysis.ts:82-88) — insertion-order
//     eviction: delete-then-set moves a re-touched key to most-recent, and
//     the OLDEST key (Map iteration order) is dropped once size > 30.
//   • loadFocus's resolution order (useSkewvoirAnalysis.ts:109-155):
//     session cache → setFiles → fetchMsrFile (the only network path).

const TREND_LIMIT = 30

interface FileFixture { msr: string }

// Mirrors useSkewvoirAnalysis.ts:82-88 (cacheFocusFile).
const cacheFocusFile = (cache: Map<string, FileFixture>, msr: string, file: FileFixture) => {
  cache.delete(msr)
  cache.set(msr, file)
  if (cache.size > TREND_LIMIT) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
}

test('cacheFocusFile bounds the cache at TREND_LIMIT (30), evicting the oldest key first', () => {
  const cache = new Map<string, FileFixture>()
  for (let i = 0; i < 35; i++) {
    cacheFocusFile(cache, `msr-${i}`, { msr: `msr-${i}` })
  }
  assert.equal(cache.size, TREND_LIMIT)
  // The first 5 inserted (msr-0..msr-4) were evicted as the oldest.
  assert.equal(cache.has('msr-0'), false)
  assert.equal(cache.has('msr-4'), false)
  // The most recently inserted 30 remain, oldest surviving is msr-5.
  assert.equal(cache.has('msr-5'), true)
  assert.equal(cache.has('msr-34'), true)
})

test('cacheFocusFile re-touching an existing key refreshes its recency instead of aging it out first', () => {
  const cache = new Map<string, FileFixture>()
  // Fill to exactly TREND_LIMIT.
  for (let i = 0; i < TREND_LIMIT; i++) {
    cacheFocusFile(cache, `msr-${i}`, { msr: `msr-${i}` })
  }
  // Re-touch the oldest key (msr-0) — this should move it to most-recent.
  cacheFocusFile(cache, 'msr-0', { msr: 'msr-0' })
  // Now insert one more NEW key — the eviction should drop msr-1 (now the
  // oldest), NOT msr-0 (just refreshed).
  cacheFocusFile(cache, 'msr-30', { msr: 'msr-30' })
  assert.equal(cache.size, TREND_LIMIT)
  assert.equal(cache.has('msr-0'), true)
  assert.equal(cache.has('msr-1'), false)
})

// Mirrors useSkewvoirAnalysis.ts:109-155 (loadFocus) — session cache → setFiles
// → network resolution order. Each source returns a tag so callers can assert
// exactly which path resolved (and therefore whether a network call happened).
type Source = 'cache' | 'set-files' | 'network'

const resolveFocusFile = (
  msr: string,
  focusCache: Map<string, FileFixture>,
  setFiles: Map<string, FileFixture>,
  networkFetch: (msr: string) => FileFixture
): { file: FileFixture, source: Source } => {
  const cached = focusCache.get(msr)
  if (cached) {
    cacheFocusFile(focusCache, msr, cached)
    return { file: cached, source: 'cache' }
  }
  const fromSet = setFiles.get(msr)
  if (fromSet) {
    cacheFocusFile(focusCache, msr, fromSet)
    return { file: fromSet, source: 'set-files' }
  }
  const res = networkFetch(msr)
  cacheFocusFile(focusCache, msr, res)
  return { file: res, source: 'network' }
}

test('resolveFocusFile hits the session cache with 0 network calls once a msr has been resolved', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>()
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  const first = resolveFocusFile('msr-a', focusCache, setFiles, networkFetch)
  assert.equal(first.source, 'network')
  assert.equal(networkCalls, 1)

  const second = resolveFocusFile('msr-a', focusCache, setFiles, networkFetch)
  assert.equal(second.source, 'cache')
  assert.equal(networkCalls, 1, 'a repeat switch to an already-resolved msr must not hit the network')
})

test('resolveFocusFile falls back to the already-fetched setFiles map (curated set) with 0 network calls', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>([['msr-b', { msr: 'msr-b' }]])
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  const result = resolveFocusFile('msr-b', focusCache, setFiles, networkFetch)
  assert.equal(result.source, 'set-files')
  assert.equal(networkCalls, 0)
  // The setFiles hit also seeds the session cache, so a later switch back is
  // a cache hit even after setFiles itself has moved on.
  assert.equal(focusCache.has('msr-b'), true)
})

test('resolveFocusFile only calls the network when both the cache and setFiles miss', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>()
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  const result = resolveFocusFile('msr-c', focusCache, setFiles, networkFetch)
  assert.equal(result.source, 'network')
  assert.equal(networkCalls, 1)
  assert.equal(focusCache.get('msr-c')?.msr, 'msr-c')
})
