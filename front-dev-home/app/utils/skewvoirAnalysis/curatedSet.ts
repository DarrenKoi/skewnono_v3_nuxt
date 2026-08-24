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

/** Whether a view renders the FOCUS measurement ALONE, even in `set` scope.
 *
 *  Two views do. The dashboard's wafer map, SEM image and radius plot are each
 *  built from ONE MsrFile, and the gallery's set-scope branch is a grid of one
 *  measurement's image files (`views/Gallery.vue`, the `focusCtx` tiles). Under
 *  a set they therefore show one member and have to be TOLD which — the left
 *  rail's 비교 세트 list is that picker, and it is interactive exactly there.
 *  The other four (position-stack, fdc, time-series, correlation) draw the
 *  whole set at once, where singling a member out changes nothing but which
 *  line is emphasised, at the cost of making a set assembled to be read
 *  TOGETHER look like a one-at-a-time list.
 *
 *  Deliberately NOT the negation of shouldLoadSet, even though the two lists
 *  nearly coincide — they answer different questions and disagree about the
 *  gallery. The gallery renders the focus alone AND still needs the batch,
 *  because `manifest.counts` feeds the rail in every view (see shouldLoadSet's
 *  note on `fdc`). Deriving one from the other would silently starve it.
 *
 *  Declared here rather than as a `activeKind === 'dashboard'` test inside the
 *  rail so adding a seventh view has ONE place to answer the question, and so
 *  the rule is reachable from `node --test` — a computed inside an SFC is not
 *  (this repo has no component-test harness). */
export const rendersFocusAlone = (activeKind: SkewvoirViewKind): boolean =>
  activeKind === 'dashboard' || activeKind === 'gallery'

/** Whether the loaded set files are the WHOLE of the set currently being asked
 *  about — the input to activeParamPool's `setComplete`.
 *
 *  Three ways a non-empty `setFiles` can still be an incomplete answer, and all
 *  three are silent — nothing throws, nothing renders an error:
 *
 *    • the batch is in flight, so the map still holds the PREVIOUS set;
 *    • the batch settled short, because /api/msr-files returns found MSRs only
 *      and skips the rest (back_dev_home/msr_file/routes.py);
 *    • the batch FAILED, which deliberately leaves the previous map in place —
 *      and two different sets of equal size would otherwise be indistinguishable
 *      by count alone, hence the key comparison rather than a size check.
 *
 *  Counting loaded-vs-expected is what a `size === 0` guard cannot express: a
 *  set that is 3-of-5 loaded is "loaded" by presence and incomplete by fact. */
export const isSetPoolComplete = (input: {
  /** A batch fetch is running. */
  pending: boolean
  /** The set key the loaded files were fetched for. */
  loadedKey: string
  /** The set key the screen is currently asking about. */
  wantedKey: string
  /** How many set files are loaded. */
  loaded: number
  /** How many the set expects. */
  expected: number
}): boolean =>
  !input.pending
  && input.loadedKey === input.wantedKey
  && input.loaded === input.expected

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

/** Whether a `set`-scope view has NOTHING of the current selection to draw yet
 *  and is still waiting on a fetch — the "show the block loading state" rule.
 *
 *  Distinct from `pending` (the file batch) on purpose, because the batch flag
 *  cannot see the FIRST half of the wait. A set is resolved by looking its URL
 *  `msrs` ids up in meas_hist, so until that history answers there is no set key
 *  to fetch files for and `pending` is legitimately false. Gating the loading
 *  state on `pending` alone therefore leaves the views rendering their EMPTY
 *  states — "비교할 측정을 추가하세요.", "이 파라미터의 sequence 데이터가
 *  없습니다." — for the whole history round-trip, which reads as an answer
 *  ("your set is empty") rather than as a wait.
 *
 *  `loaded === 0` is what keeps this to the COLD path. A set edit over an
 *  already-loaded set carries the previous files (see the incremental branch in
 *  useSkewvoirAnalysis), so the charts stay on screen and the in-panel inline
 *  spinner is the right feedback there — swapping a rendered chart for a block
 *  loader on every add/remove would be a worse trade. */
export const isSetColdLoading = (input: {
  /** The screen wants the curated set at all (shouldLoadSet). */
  wantSet: boolean
  /** How many set files are loaded, for ANY set. */
  loaded: number
  /** The meas_hist fetch that resolves the set's rows is running. */
  historyPending: boolean
  /** The msr_file batch is running. */
  filesPending: boolean
}): boolean =>
  input.wantSet
  && input.loaded === 0
  && (input.historyPending || input.filesPending)

/** Whether the manifest's compatibility count (the rail's 호환 chip) is an
 *  answer at all, or a number produced by having nothing to count.
 *
 *  `buildAnalysisManifest` derives `counts.compatible` from the files that
 *  LOADED, and the focus file loads on its own path (loadFocus, not the set
 *  batch). So with no set files in hand the manifest compares the focus against
 *  itself, finds it compatible, and reports 호환 1 — which beside a 9-member
 *  member list reads as "8 of your 9 are incompatible", a verdict nothing
 *  computed.
 *
 *  Two situations reach that state, and only one of them ends:
 *
 *    • a cold set load, for as long as meas_hist + the msr_file batch take;
 *    • the Dashboard, PERMANENTLY. It is excluded from shouldLoadSet to keep
 *      the single-measurement lazy-load invariant, so under `set` scope its
 *      rail has a full member list and will never have a file to compare them
 *      with. A "wait for the fetch" flag cannot cover this one — there is no
 *      fetch to wait for.
 *
 *  Hence `loaded`, not a pending flag: the question is whether anything was
 *  counted, not whether something is in flight. That also leaves a warm set
 *  edit alone — it carries the previous files, so the chip HOLDS the last real
 *  answer for the second the batch takes instead of blinking to a placeholder.
 *
 *  A one-measurement selection is always known: `호환 1` is then the whole
 *  truth, not a floor. */
export const isSetCompatibilityKnown = (input: {
  /** How many measurements the selection names (URL `msrs`). */
  members: number
  /** How many set files are loaded, for ANY set. */
  loaded: number
}): boolean => input.members < 2 || input.loaded > 0
