// Skewvoir analysis — focus-file resolution (session cache + staleness guard).
//
// The overview focus-switcher chip strip lets a user hop between the curated
// set's measurements. Each hop needs ONE MsrFile; this module decides where it
// comes from so a hop back to a just-viewed measurement costs 0 requests:
//
//   session cache → the curated set's already-fetched files → network
//
// The cache is bounded at TREND_LIMIT with insertion-order (LRU) eviction, so
// the whole curated set — capped at the same limit — fits without evicting
// anything mid-session.
//
// Pure and framework-free (mirrors utils/skewvoirAnalysis/setEditing.ts); the
// only mutation is on the Map the caller hands in. `composables/
// useSkewvoirAnalysis.ts` owns the refs, the await, and the network call.
//
// Generic in the file: this decides WHERE a focus file comes from, never what
// one contains, so it stays independent of the MsrFileResponse schema.
import { TREND_LIMIT } from './curatedSet.ts'

/** Which in-memory source answered a focus-file lookup. `null` from
 *  lookupFocusFile means both missed and the network is the only path left. */
export type FocusFileSource = 'cache' | 'set-files'

export interface FocusFileHit<T> {
  file: T
  source: FocusFileSource
}

/** Store a focus file under `msr`, bounding the cache at TREND_LIMIT.
 *
 *  Delete-then-set moves an existing key to the most-recently-inserted position
 *  in Map iteration order, so re-touching a cached msr counts as fresh recency
 *  rather than aging out first. Once the cache overflows, the OLDEST key is
 *  dropped. */
export const cacheFocusFile = <T>(cache: Map<string, T>, msr: string, file: T): void => {
  cache.delete(msr)
  cache.set(msr, file)
  if (cache.size > TREND_LIMIT) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
}

/** Resolve a focus file from memory alone: session cache first, then the
 *  curated set's already-fetched files. Returns `null` when both miss — the
 *  caller's network fetch is the ONLY remaining path. Read-only: the caller
 *  decides when to touch the cache. */
export const lookupFocusFile = <T>(
  msr: string,
  cache: ReadonlyMap<string, T>,
  setFiles: ReadonlyMap<string, T>
): FocusFileHit<T> | null => {
  const cached = cache.get(msr)
  if (cached) return { file: cached, source: 'cache' }
  const fromSet = setFiles.get(msr)
  if (fromSet) return { file: fromSet, source: 'set-files' }
  return null
}

/** The stale-response guard: is the msr a resolved result was requested for
 *  still the one the URL is focused on?
 *
 *  A→B→A genuinely races because the MsrFile fetch has only in-flight dedupe, no
 *  completed-response cache. The requested msr is captured before the await, and
 *  a result that fails this test is DISCARDED, so a slow B never overwrites the
 *  A the user is back on. */
export const isFocusStillCurrent = (
  currentMsr: string | undefined,
  requestedMsr: string
): boolean => currentMsr === requestedMsr
