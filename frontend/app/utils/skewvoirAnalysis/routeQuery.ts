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
import type { AnalysisScope, SequenceAxisMode, TsAxisMode, TsBaseline, TsView } from './types.ts'
import { DEFAULT_RANGE, DEFAULT_STDDEV, type MethodConfig } from '../anomaly/types.ts'

export const DEFAULT_VIEW: SkewvoirViewKind = 'dashboard'

const VIEW_KINDS: readonly SkewvoirViewKind[] = [
  'dashboard',
  'position-stack',
  'fdc',
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
  const parts = ids.length ? ids : (fallback ? [fallback] : [])
  // A duplicated msr would be counted twice by every aggregation (mean, n,
  // coverage) and would also consume one of the TREND_LIMIT slots, so ids are
  // unique from the moment they leave the URL.
  return [...new Set(parts)]
}

/** The hand-picked BASELINE group (`base=id,id`): the members of the curated
 *  set the rest are compared against. Read as an intersection with `msrs`, so
 *  an id edited out of the set drops off the baseline without a second write.
 *  Not `ref` (reference parameter) and not `tsb` (the Time-Series residual
 *  baseline) — both names were taken. */
export const parseBaseline = (query: LocationQuery): string[] => {
  const set = new Set(parseMsrList(query))
  const ids = (qstr(query.base) ?? '').split(',').map(s => s.trim())
  return [...new Set(ids)].filter(id => set.has(id))
}

/** Write-side mirror: no baseline maps to `null` (same rule as encodeFdcAxis). */
export const encodeBaseline = (ids: readonly string[]): string | null =>
  ids.length ? ids.join(',') : null

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

/** SequenceAxisMode → URL value, the write-side mirror of parseFdcAxis (same
 *  shape as encodeParam/decodeParam above). The default `'param'` maps to
 *  `null` — a RULE, not an implementation detail: the default must leave the
 *  URL clean, so only the `'all'` opt-out is ever written. */
export const encodeFdcAxis = (mode: SequenceAxisMode): string | null =>
  mode === 'all' ? 'all' : null

export const DEFAULT_TS_VIEW: TsView = 'trend'
export const DEFAULT_TS_AXIS: TsAxisMode = 'time'
export const DEFAULT_TS_BASELINE: TsBaseline = 'raw'

const TS_VIEWS: readonly TsView[] = ['trend', 'dist', 'skew']
const TS_AXES: readonly TsAxisMode[] = ['time', 'order', 'eqp']
const TS_BASELINES: readonly TsBaseline[] = ['raw', 'resid']

/** Lens for the Time-Series view. An unknown value corrects to `trend` rather
 *  than rendering nothing, matching parseView's treatment of a hand-edited link. */
export const parseTsView = (raw: unknown): TsView => {
  const v = qstr(raw)
  return v && (TS_VIEWS as readonly string[]).includes(v) ? v as TsView : DEFAULT_TS_VIEW
}

export const parseTsAxis = (raw: unknown): TsAxisMode => {
  const v = qstr(raw)
  return v && (TS_AXES as readonly string[]).includes(v) ? v as TsAxisMode : DEFAULT_TS_AXIS
}

export const parseTsBaseline = (raw: unknown): TsBaseline => {
  const v = qstr(raw)
  return v && (TS_BASELINES as readonly string[]).includes(v) ? v as TsBaseline : DEFAULT_TS_BASELINE
}

/** Write-side mirrors of the three parsers above, same shape as encodeFdcAxis:
 *  the DEFAULT maps to `null` so the key is cleared from the URL. Same RULE, and
 *  the reason it is a rule rather than tidiness — every shared Time-Series link
 *  would otherwise carry `tsview=trend&tsx=time&tsb=raw`, three params that say
 *  nothing the absent key does not already say. Each reads its default from the
 *  SAME constant its parser falls back to, so the round trip cannot drift. */
export const encodeTsView = (v: TsView): string | null =>
  v === DEFAULT_TS_VIEW ? null : v

export const encodeTsAxis = (v: TsAxisMode): string | null =>
  v === DEFAULT_TS_AXIS ? null : v

export const encodeTsBaseline = (v: TsBaseline): string | null =>
  v === DEFAULT_TS_BASELINE ? null : v

/** The radial trend degree (`rfit`). 측정 개요's Radius Plot and 위치 비교's
 *  residual layer fit the SAME wafer, so they read one value — held per panel,
 *  the two views disagreed about which sites sit off the trend. Only the
 *  degrees the Radius Plot toggle offers travel; anything else is linear. */
export type SharedRadialModel = 'linear' | 'quadratic' | 'cubic'

export const parseRadialModel = (raw: unknown): SharedRadialModel => {
  const v = qstr(raw)
  return v === 'quadratic' || v === 'cubic' ? v : 'linear'
}

export const encodeRadialModel = (model: SharedRadialModel): string | null =>
  model === 'linear' ? null : model

/** The anomaly thresholds, URL-carried as `anom=<method>:<watch>:<abnormal>`.
 *  They decide every verdict on the screen (site judgements on 측정 개요, the
 *  Time-Series trend, the across-MSR feature rows), so two people opening the
 *  same link must be judging by the same numbers — held anywhere else, the link
 *  reproduces the data and silently not the verdict.
 *
 *  Only the ACTIVE method's pair travels: the other method's thresholds judge
 *  nothing, so it keeps its defaults. Anything malformed (unknown method, a
 *  non-positive threshold, watch above abnormal) reads as the defaults — a
 *  hand-edited link must never judge by garbage. */
export const parseAnomalyCfg = (raw: unknown): MethodConfig => {
  const cfg: MethodConfig = { method: 'range', range: { ...DEFAULT_RANGE }, stddev: { ...DEFAULT_STDDEV } }
  const [method, w, a, ...rest] = (qstr(raw) ?? '').split(':')
  const watch = Number(w)
  const abnormal = Number(a)
  if (rest.length || !w || !a || !(watch > 0) || !(abnormal >= watch) || !Number.isFinite(abnormal)) return cfg
  if (method === 'range') return { ...cfg, range: { ...cfg.range, watchPct: watch, abnormalPct: abnormal } }
  if (method === 'stddev') return { ...cfg, method, stddev: { watchK: watch, abnormalK: abnormal } }
  return cfg
}

/** A method's (watch, abnormal) pair — the active method's unless one is named. */
export const thresholdPair = (cfg: MethodConfig, method = cfg.method): { watch: number, abnormal: number } =>
  method === 'range'
    ? { watch: cfg.range.watchPct, abnormal: cfg.range.abnormalPct }
    : { watch: cfg.stddev.watchK, abnormal: cfg.stddev.abnormalK }

/** Write-side mirror: the default maps to `null` (same rule as encodeFdcAxis). */
export const encodeAnomalyCfg = (cfg: MethodConfig): string | null => {
  const { watch, abnormal } = thresholdPair(cfg)
  const isDefault = cfg.method === 'range'
    && watch === DEFAULT_RANGE.watchPct && abnormal === DEFAULT_RANGE.abnormalPct
  return isDefault ? null : `${cfg.method}:${watch}:${abnormal}`
}

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
  // A set link carries no mp: the selection's mp is the search landing's WAFER
  // placeholder, not a pick, and resolveActiveParam would honour it over the
  // coverage ranking whenever any one set member carries it.
  ...(scope === 'set' ? {} : { mp: encodeParam(sel.mp) }),
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
