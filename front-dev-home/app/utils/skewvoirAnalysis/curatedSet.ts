// Skewvoir analysis — the curated comparison set (URL `msrs`).
//
// The set is EXPLICIT: the user picks which measurements sit alongside the
// focus, and the picks travel in the link. This module answers the two pure
// questions the analysis composable asks about it — should the set's files be
// fetched at all, and which meas_hist rows does the URL list resolve to.
//
// Pure and framework-free (mirrors utils/skewvoirAnalysis/setEditing.ts) so
// both rules are unit-testable without a Nuxt runtime.
import type { SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'
import type { AnalysisScope } from './types.ts'

/** Cap the multi-measurement trend so a high-volume recipe doesn't fan out into
 *  hundreds of MsrFile fetches. Also bounds the focus-file session cache
 *  (focusCache.ts), so a chip strip switching among the curated set fits
 *  entirely in the cache without evicting anything mid-session. */
export const TREND_LIMIT = 30

/** Whether the curated set's MsrFiles should be batch-fetched.
 *
 *  The set is shared across ALL non-dashboard detail views (position-stack /
 *  time-series / correlation / gallery / fdc) whenever the analysis is in
 *  `set` scope, so a set edited in one view is present in the others.
 *  Dashboard stays excluded to preserve the single-measurement lazy-load
 *  invariant (no set fan-out), and a `single`-scope screen never triggers the
 *  batch fetch either.
 *
 *  `fdc` included is deliberate, not an oversight of the exclusion-by-default
 *  shape below: the FDC view renders only its empty state under `set` scope
 *  (single-MSR sequence workbench moved out to be `fdc`'s single-scope
 *  content — see views/Fdc.vue), so the fetch itself goes unused there. But
 *  `manifest.counts` feeds the left rail in EVERY view regardless of which
 *  one is active, so excluding `fdc` here would starve the rail the one time
 *  a user opens that tab under `set` scope. */
export const shouldLoadSet = (scope: AnalysisScope, activeKind: SkewvoirViewKind): boolean =>
  scope === 'set' && activeKind !== 'dashboard'

/** Resolve the URL `msrs` list against a meas_hist row lookup, in the list's
 *  AUTHORED order (never sorted). Ids with no matching row are dropped, and the
 *  result is capped defensively at TREND_LIMIT.
 *
 *  Generic in the row: this decides WHICH measurements are in the set, never
 *  what a row contains, so it stays independent of the MeasHistRow schema. */
export const resolveSetRows = <T>(
  msrList: readonly string[],
  rowByMsr: ReadonlyMap<string, T>
): T[] =>
  msrList
    .map(id => rowByMsr.get(id))
    .filter((r): r is T => r != null)
    .slice(0, TREND_LIMIT)
