import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cacheFocusFile, isFocusStillCurrent, lookupFocusFile, type FocusFileSource } from './focusCache.ts'
import { TREND_LIMIT } from './curatedSet.ts'

interface FileFixture { msr: string }

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

// loadFocus (useSkewvoirAnalysis.ts) falls back to the network only when
// lookupFocusFile misses, and caches whatever it ends up with. `resolve` below
// is a TEST DRIVER for exactly that fallback — it deliberately omits loadFocus's
// ref/pending/staleness handling — so a fake fetcher can count how many focus
// switches actually reach the network. The resolution ORDER under test is the
// imported lookupFocusFile's, not this driver's.
const resolve = (
  msr: string,
  focusCache: Map<string, FileFixture>,
  setFiles: Map<string, FileFixture>,
  networkFetch: (msr: string) => FileFixture
): { file: FileFixture, source: FocusFileSource | 'network' } => {
  const hit = lookupFocusFile(msr, focusCache, setFiles)
  const file = hit?.file ?? networkFetch(msr)
  cacheFocusFile(focusCache, msr, file)
  return { file, source: hit?.source ?? 'network' }
}

test('a focus file resolves from the session cache with 0 network calls once a msr has been resolved', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>()
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  const first = resolve('msr-a', focusCache, setFiles, networkFetch)
  assert.equal(first.source, 'network')
  assert.equal(networkCalls, 1)

  const second = resolve('msr-a', focusCache, setFiles, networkFetch)
  assert.equal(second.source, 'cache')
  assert.equal(networkCalls, 1, 'a repeat switch to an already-resolved msr must not hit the network')
})

test('a focus file falls back to the already-fetched setFiles map (curated set) with 0 network calls', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>([['msr-b', { msr: 'msr-b' }]])
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  const result = resolve('msr-b', focusCache, setFiles, networkFetch)
  assert.equal(result.source, 'set-files')
  assert.equal(networkCalls, 0)
  // The setFiles hit also seeds the session cache, so a later switch back is
  // a cache hit even after setFiles itself has moved on.
  assert.equal(focusCache.has('msr-b'), true)
})

test('the network is the only path left when both the cache and setFiles miss', () => {
  const focusCache = new Map<string, FileFixture>()
  const setFiles = new Map<string, FileFixture>()
  let networkCalls = 0
  const networkFetch = (msr: string): FileFixture => {
    networkCalls++
    return { msr }
  }

  assert.equal(lookupFocusFile('msr-c', focusCache, setFiles), null)
  const result = resolve('msr-c', focusCache, setFiles, networkFetch)
  assert.equal(result.source, 'network')
  assert.equal(networkCalls, 1)
  assert.equal(focusCache.get('msr-c')?.msr, 'msr-c')
})

test('lookupFocusFile prefers the session cache over setFiles when both hold the msr', () => {
  const focusCache = new Map<string, FileFixture>([['msr-d', { msr: 'msr-d' }]])
  const setFiles = new Map<string, FileFixture>([['msr-d', { msr: 'msr-d' }]])
  assert.equal(lookupFocusFile('msr-d', focusCache, setFiles)?.source, 'cache')
})

test('the stale-guard discards a focus result whose requested msr is no longer the current URL msr', () => {
  // Requested B, but the URL is back on A by the time B resolves → discard B.
  assert.equal(isFocusStillCurrent('msr-a', 'msr-b'), false)
  // No selection at all is never a match either.
  assert.equal(isFocusStillCurrent(undefined, 'msr-b'), false)
})

test('the stale-guard keeps a focus result whose requested msr still matches the current URL msr', () => {
  assert.equal(isFocusStillCurrent('msr-b', 'msr-b'), true)
})
