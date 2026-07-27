// Skewvoir analysis — pure URL-query ⇄ analysis-state translation.
//
// The analysis workspace keeps no private copy of "what am I looking at": the
// URL query is the single source of truth, which is exactly what makes an
// analysis screen shareable (paste the link, get the same screen — a live
// re-query, not a frozen snapshot). Everything here READS a query, BUILDS a
// query, or PATCHES a query; `composables/useSkewvoirRoute.ts` is the thin
// wrapper that binds these to `useRoute()` / `router.replace()` / `navigateTo`.
//
// Pure and framework-free (mirrors utils/skewvoirAnalysis/setEditing.ts) so the
// parsing/normalisation rules are unit-testable without a Nuxt runtime.
//
// Runs under raw `node --test` — sibling imports carry an explicit `.ts`
// extension, and every framework import is type-only (erased at runtime).
import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import type { SkewvoirSelection, SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'
import type { AnalysisScope, SequenceAxisMode } from './types.ts'

export const DEFAULT_VIEW: SkewvoirViewKind = 'dashboard'

const VIEW_KINDS: readonly SkewvoirViewKind[] = [
  'dashboard',
  'position-stack',
  'time-series',
  'correlation',
  'gallery'
]

/** A three-valued in-place query patch. Per key:
 *  - `string`    → write the value
 *  - `null`      → CLEAR the param from the URL
 *  - `undefined` → leave the existing value UNTOUCHED */
export type QueryPatch = Record<string, string | null | undefined>

/** A LocationQueryValue may be `string | string[] | null`; collapse it to a
 *  usable string. An array collapses to its first element and an empty string
 *  collapses to `undefined`, so "present but blank" is treated as absent. */
export const qstr = (v: unknown): string | undefined => {
  const first = Array.isArray(v) ? v[0] : v
  return typeof first === 'string' && first.length > 0 ? first : undefined
}

/** The UNNAMED dummy MP: a settling point measured before the real MPs, so the
 *  tool is stable by the time the recipe's parameters are measured. It carries
 *  real rows and real IMAGES to review, so it has to be selectable like any
 *  other parameter — but its name is the empty string, and `qstr` (correctly)
 *  reads a blank query value as ABSENT. Selecting it would therefore be
 *  unrepresentable in the URL, which is the single source of truth for what the
 *  workspace is looking at.
 *
 *  So `mp` carries a reserved SENTINEL for it. The token is parenthesised, and
 *  tool parameter names are bare identifiers (CD_TOP, SIDEWALL_ANGLE, WAFER…),
 *  so it cannot collide with a real parameter name.
 *
 *  Scope: `mp` only. The Correlation `x`/`y` axes keep '' meaning "unset", and
 *  their pickers list named parameters only — pairing a one-shot dummy against
 *  a real parameter has no meaning, and conflating "unset" with "the unnamed
 *  one" is exactly the bug this sentinel exists to avoid. */
export const UNNAMED_PARAM = ''
export const UNNAMED_PARAM_TOKEN = '(unnamed)'

/** URL value → parameter name (the sentinel becomes the empty name). */
export const decodeParam = (raw: unknown): string | undefined => {
  const v = qstr(raw)
  return v === UNNAMED_PARAM_TOKEN ? UNNAMED_PARAM : v
}

/** Parameter name → URL value (the empty name becomes the sentinel). */
export const encodeParam = (parameter: string): string =>
  parameter === UNNAMED_PARAM ? UNNAMED_PARAM_TOKEN : parameter

const isViewKind = (v: string): v is SkewvoirViewKind =>
  (VIEW_KINDS as readonly string[]).includes(v)

/** The active view, whitelisted against VIEW_KINDS — an unrecognized (or
 *  missing) `view` param falls back to the Dashboard rather than rendering
 *  nothing for a hand-edited link. */
export const parseView = (raw: unknown): SkewvoirViewKind => {
  const v = qstr(raw)
  return v && isViewKind(v) ? v : DEFAULT_VIEW
}

/** Rebuild the selection from the query. No `lot` => no selection (empty
 *  state). `mp` defaults to WAFER and `cap` to the em-dash placeholder.
 *  `mp` goes through decodeParam, so the unnamed-MP sentinel comes back as the
 *  empty name (and only the sentinel does — a genuinely absent `mp` still
 *  defaults to WAFER). */
export const parseSelection = (query: LocationQuery): SkewvoirSelection | null => {
  const lot = qstr(query.lot)
  if (!lot) return null
  return {
    lot,
    recipe: qstr(query.recipe) ?? '',
    eq: qstr(query.eq) ?? '',
    mp: decodeParam(query.mp) ?? 'WAFER',
    msr: qstr(query.msr) ?? '',
    capturedAt: qstr(query.cap) ?? '—'
  }
}

/** The comparison set — an EXPLICIT, user-curated list of msr ids carried in
 *  the URL (`?msrs=a,b,c`). Ids are trimmed and empties dropped; when the list
 *  is absent or empty after trimming it falls back to the single focus `msr`
 *  so a one-pick screen still renders. */
export const parseMsrList = (query: LocationQuery): string[] => {
  const raw = qstr(query.msrs)
  const ids = raw ? raw.split(',').map(s => s.trim()).filter(Boolean) : []
  const fallback = qstr(query.msr)
  return ids.length ? ids : (fallback ? [fallback] : [])
}

/** Analysis scope — held in the URL SEPARATELY from the selection count so a
 *  single-focus screen can still be an explicit `set` (comparison-ready) and a
 *  multi-msr link can be forced back to `single`. Normalisation: an explicit
 *  `scope=single|set` always wins; when ABSENT (every link authored before this
 *  param existed) it is DERIVED from the set size so old links keep working. */
export const parseScope = (query: LocationQuery): AnalysisScope => {
  const explicit = qstr(query.scope)
  if (explicit === 'single' || explicit === 'set') return explicit
  return parseMsrList(query).length > 1 ? 'set' : 'single'
}

/** Which sequence axis the FDC 분석 panes use. Absent means the default
 *  parameter-scoped axis, so a plain analysis link stays free of the param;
 *  `all` opts into the whole-MSR union. An unrecognised value falls back to the
 *  default rather than rendering an axis nobody implemented. */
export const parseFdcAxis = (raw: unknown): SequenceAxisMode =>
  qstr(raw) === 'all' ? 'all' : 'param'

/** Serialize a selection (+ view + explicit set + scope) into an analysis-link
 *  query. `msrs` defaults to the focus alone; pass a curated list for the
 *  comparison set. `scope` is emitted only when given, so a plain single-pick
 *  link stays free of the param and keeps deriving its scope from the set. */
export const toAnalysisQuery = (
  sel: SkewvoirSelection,
  view: SkewvoirViewKind = DEFAULT_VIEW,
  msrs?: string[],
  scope?: AnalysisScope
) => ({
  lot: sel.lot,
  recipe: sel.recipe,
  eq: sel.eq,
  mp: encodeParam(sel.mp),
  msr: sel.msr,
  msrs: (msrs && msrs.length ? msrs : [sel.msr]).filter(Boolean).join(','),
  cap: sel.capturedAt,
  view,
  ...(scope ? { scope } : {})
})

/** Apply a QueryPatch to an existing query. Every param NOT named in the patch
 *  is preserved, which is what lets a focus move rewrite `msr` without losing
 *  `msrs` / `view` / `mp`. */
export const applyQueryPatch = (query: LocationQuery, patch: QueryPatch): LocationQueryRaw => {
  const cleared = new Set(
    Object.entries(patch).filter(([, v]) => v === null).map(([k]) => k)
  )
  const next: LocationQueryRaw = {}
  for (const [key, value] of Object.entries(query)) {
    if (!cleared.has(key)) next[key] = value
  }
  for (const [key, value] of Object.entries(patch)) {
    if (typeof value === 'string') next[key] = value
  }
  return next
}

/** The focus MSR plus the identity fields the left rail renders beside it — and
 *  itself a QueryPatch, so moving the focus is one applyQueryPatch: it rewrites
 *  `msr` + `lot`/`eq`/`cap` while PRESERVING `msrs`/`view`/`mp`. Absent fields
 *  are `undefined`, which leaves the existing (still correct) URL value alone
 *  rather than blanking it. */
export type FocusIdentity = {
  msr: string
  lot?: string
  eq?: string
  cap?: string
}

/** The subset of a meas_hist row that carries the focus identity. */
export interface FocusIdentityRow {
  lot_id: string
  eqp_id: string
  timestamp: string
}

/** Map a meas_hist row onto the focus identity. A deep-link MSR with no row
 *  yields all-`undefined` identity fields — the existing URL values stand. */
export const focusIdentityFromRow = (
  msr: string,
  row: FocusIdentityRow | undefined
): FocusIdentity => ({
  msr,
  lot: row?.lot_id,
  eq: row?.eqp_id,
  cap: row?.timestamp
})
