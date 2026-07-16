// Skewvoir analysis — cross-MSR compatibility (framework-free, pure).
//
// Runs under raw `node --test` (no Nuxt, no bundler), so every sibling import
// carries an explicit `.ts` extension and nothing here touches Nuxt runtime.
//
// The whole module obeys the unknown-safe contract documented in ./types.ts:
// a field gates matching ONLY when both sides are known and equal; `unknown`
// never equals `unknown`, and per-row-varying fields are never collapsed to a
// fabricated single value.

import type {
  AnalysisManifest,
  AnalysisScope,
  CanonicalSiteKey,
  CompatibilityGroup,
  CompatibilitySignature,
  ExclusionEntry,
  ExclusionReason,
  FieldSet,
  Maybe,
  Readiness,
  ReadinessMatrix,
  RecipeIdentity
} from './types.ts'

// ── Source shape ─────────────────────────────────────────────────────────────
// A structural subset of MsrFileResponse. The live response satisfies this, and
// the two office-gated fields (recipe_revision, site_layout_hash) are optional
// so they read as UNKNOWN whenever the current mock omits them.

export interface SignatureSourceRow {
  parameter: string
  meas_method?: string | null
  object_type?: string | null
  meas_kind?: string | null
  meas_condition_mag?: number | null
  meas_condition_vac?: number | null
  meas_condition_pixel?: string | null
}

export interface SignatureSourceExe {
  recipe_name?: string | null
  idp_name?: string | null
  idw_name?: string | null
  wafer_size?: string | null
  chip_array?: string | null
  chip_pitch?: string | null
  map_offset?: string | null
  map_origin?: string | null
  // Office-gated — absent in Phase-1 mock.
  recipe_revision?: string | null
  site_layout_hash?: string | null
}

export interface SignatureSource {
  msr: string
  exe_detail_info?: SignatureSourceExe
  parameters?: { parameter: string, unit?: string | null }[]
  rows?: SignatureSourceRow[]
}

// ── Unknown-safe constructors ────────────────────────────────────────────────

const known = <T>(value: T): Maybe<T> => ({ state: 'known', value })
const UNKNOWN: Maybe<never> = { state: 'unknown' }

/** Wrap a possibly-absent scalar: non-empty → known, else unknown. */
const maybe = <T>(value: T | null | undefined): Maybe<T> =>
  value === null || value === undefined || value === '' ? UNKNOWN : known(value)

/** Reduce a list of candidate values (nulls/sentinels already stripped) into a
 * FieldSet — the honest single/mixed/unknown state. */
const toFieldSet = <T>(values: T[]): FieldSet<T> => {
  const distinct = [...new Set(values)]
  if (distinct.length === 0) return { state: 'unknown' }
  if (distinct.length === 1) return { state: 'single', value: distinct[0]! }
  return { state: 'mixed', values: distinct }
}

// ── Signature extraction ─────────────────────────────────────────────────────

const recipeIdentity = (exe: SignatureSourceExe | undefined): Maybe<RecipeIdentity> => {
  const name = exe?.recipe_name
  if (name === null || name === undefined || name === '') return UNKNOWN
  return known({
    recipeName: name,
    idpName: maybe(exe?.idp_name),
    idwName: maybe(exe?.idw_name)
  })
}

export function extractSignature(source: SignatureSource, parameter: string): CompatibilitySignature {
  const exe = source.exe_detail_info
  const rows = (source.rows ?? []).filter(r => r.parameter === parameter)
  // Fall back to all rows if the parameter labels don't match any row, so the
  // acquisition context is still derived rather than silently blanked.
  const scoped = rows.length > 0 ? rows : (source.rows ?? [])

  const unitEntry = (source.parameters ?? []).find(p => p.parameter === parameter)

  // Per-row-varying fields — strip empty-row sentinels (0 mag/vac, "0,0" pixel,
  // null kind) so a metadata-only row can't pollute the set with junk values.
  const nums = (pick: (r: SignatureSourceRow) => number | null | undefined): number[] =>
    scoped.map(pick).filter((v): v is number => typeof v === 'number' && v > 0)
  const strs = (pick: (r: SignatureSourceRow) => string | null | undefined, drop: string[] = []): string[] =>
    scoped.map(pick).filter((v): v is string => typeof v === 'string' && v !== '' && !drop.includes(v))

  return {
    msr: source.msr,
    parameter,
    recipe: recipeIdentity(exe),
    recipeRevision: maybe(exe?.recipe_revision),
    unit: maybe(unitEntry?.unit),
    measMethod: toFieldSet(strs(r => r.meas_method)),
    objectType: toFieldSet(strs(r => r.object_type)),
    measKind: toFieldSet(strs(r => r.meas_kind)),
    mag: toFieldSet(nums(r => r.meas_condition_mag)),
    vac: toFieldSet(nums(r => r.meas_condition_vac)),
    pixel: toFieldSet(strs(r => r.meas_condition_pixel, ['0,0'])),
    coordinate: {
      waferSize: maybe(exe?.wafer_size),
      chipArray: maybe(exe?.chip_array),
      chipPitch: maybe(exe?.chip_pitch),
      mapOffset: maybe(exe?.map_offset),
      mapOrigin: maybe(exe?.map_origin)
    },
    siteLayoutHash: maybe(exe?.site_layout_hash)
  }
}

// ── Comparison ───────────────────────────────────────────────────────────────

/** A genuine conflict: both known and DIFFERENT. Unknown is never a conflict. */
const knownConflict = <T>(a: Maybe<T>, b: Maybe<T>): boolean =>
  a.state === 'known' && b.state === 'known' && a.value !== b.value

/** A per-row-varying field conflicts only when BOTH sides are single-valued and
 * different — a `mixed` or `unknown` side can never be a fabricated conflict. */
const fieldSetConflict = <T>(a: FieldSet<T>, b: FieldSet<T>): boolean =>
  a.state === 'single' && b.state === 'single' && a.value !== b.value

/**
 * Reasons a candidate is incompatible with the reference (empty = compatible).
 * The focus/reference is assumed extractable; a candidate that lost its recipe
 * identity is `metadata-missing` (we cannot establish compatibility at all).
 */
export function compareToReference(
  reference: CompatibilitySignature,
  candidate: CompatibilitySignature
): ExclusionReason[] {
  const reasons: ExclusionReason[] = []

  if (candidate.recipe.state !== 'known' || candidate.unit.state !== 'known') {
    reasons.push('metadata-missing')
    return reasons
  }

  const refName: Maybe<string> = reference.recipe.state === 'known'
    ? known(reference.recipe.value.recipeName)
    : UNKNOWN
  const candName = known(candidate.recipe.value.recipeName)
  if (knownConflict(refName, candName)) reasons.push('recipe-mismatch')

  if (knownConflict(reference.unit, candidate.unit)) reasons.push('unit-mismatch')
  if (fieldSetConflict(reference.measMethod, candidate.measMethod)) reasons.push('method-mismatch')
  if (knownConflict(reference.siteLayoutHash, candidate.siteLayoutHash)) reasons.push('layout-mismatch')

  return reasons
}

// ── Grouping ─────────────────────────────────────────────────────────────────

const fieldKey = <T>(m: Maybe<T>): string => (m.state === 'known' ? String(m.value) : '∅')

const groupKey = (sig: CompatibilitySignature): string => {
  const recipe = sig.recipe.state === 'known' ? sig.recipe.value.recipeName : '∅'
  return [recipe, fieldKey(sig.unit), fieldKey(sig.siteLayoutHash)].join('|')
}

// ── Layout-dependent readiness ───────────────────────────────────────────────

const intersect = (sets: ReadonlySet<string>[]): Set<string> => {
  const first = sets[0]
  if (!first) return new Set()
  let acc = new Set<string>(first)
  for (const s of sets.slice(1)) acc = new Set([...acc].filter(x => s.has(x)))
  return acc
}
const union = (sets: ReadonlySet<string>[]): Set<string> => {
  const all = new Set<string>()
  for (const s of sets) s.forEach(x => all.add(x))
  return all
}

/**
 * Readiness of any capability that needs a shared physical site layout across
 * the included set. Three gates, in order:
 *  - all layout hashes known AND equal  → `ready`
 *  - site-key sets partially overlap     → `limited` (common-coverage:N)
 *  - otherwise (unknown/absent layout)   → `unavailable`
 * A set of fewer than two MSRs is always `unavailable` (nothing to relate).
 */
function layoutReadiness(
  signatures: CompatibilitySignature[],
  siteKeys?: Map<string, ReadonlySet<string>>
): Readiness {
  if (signatures.length < 2) {
    return { status: 'unavailable', reasons: ['needs-multiple-msrs'] }
  }

  const hashes = signatures.map(s => s.siteLayoutHash)
  const allKnown = hashes.every(h => h.state === 'known')
  if (allKnown) {
    const first = (hashes[0] as { state: 'known', value: string }).value
    const allEqual = hashes.every(h => (h as { state: 'known', value: string }).value === first)
    if (allEqual) return { status: 'ready', reasons: [] }
  }

  if (siteKeys) {
    const sets = signatures.map(s => siteKeys.get(s.msr) ?? new Set<string>())
    const common = intersect(sets)
    const all = union(sets)
    if (common.size > 0 && common.size < all.size) {
      return { status: 'limited', reasons: [`common-coverage:${common.size}`] }
    }
  }

  return {
    status: 'unavailable',
    reasons: [allKnown ? 'layout-mismatch' : 'layout-unknown']
  }
}

// ── Manifest ─────────────────────────────────────────────────────────────────

export interface AnalysisManifestOptions {
  // MSRs the user selected. When some fail to load, this exceeds `files`; when
  // omitted, selection is assumed equal to what loaded.
  requestedMsrs?: string[]
  // Layout-independent site identities per MSR, used only to compute `limited`
  // common-coverage readiness. Absent in the Phase-1 mock flow → unavailable.
  siteKeys?: Map<string, ReadonlySet<string>>
}

/**
 * Compute inclusion / exclusion / groups / readiness for an analysis selection.
 *
 * `files` are the MSRs that actually loaded (the focus among them). Exclusions
 * are drawn from these; MSRs that failed to load are only reflected in the
 * `selected` count, never in `excluded`.
 */
export function buildAnalysisManifest(
  focus: string,
  files: SignatureSource[],
  parameter: string,
  options: AnalysisManifestOptions = {}
): AnalysisManifest {
  const requested = options.requestedMsrs ?? files.map(f => f.msr)
  const signatures = files.map(f => extractSignature(f, parameter))
  const byMsr = new Map(signatures.map(s => [s.msr, s]))

  const reference = byMsr.get(focus) ?? signatures[0]

  const included: string[] = []
  const excluded: ExclusionEntry[] = []

  for (const sig of signatures) {
    if (reference && sig.msr === reference.msr) {
      included.push(sig.msr)
      continue
    }
    const reasons = reference ? compareToReference(reference, sig) : ['metadata-missing' as ExclusionReason]
    if (reasons.length === 0) included.push(sig.msr)
    else excluded.push({ msr: sig.msr, reasons })
  }

  const includedSigs = included
    .map(msr => byMsr.get(msr))
    .filter((s): s is CompatibilitySignature => s != null)

  const groups = buildGroups(includedSigs)
  const readinessValue = layoutReadiness(includedSigs, options.siteKeys)
  const readiness: ReadinessMatrix = {
    multiMsrDelta: readinessValue,
    siteVariability: readinessValue,
    sameSiteGallery: readinessValue
  }

  const scope: AnalysisScope = requested.length > 1 ? 'set' : 'single'

  return {
    scope,
    parameter,
    focus,
    requested,
    loaded: signatures.map(s => s.msr),
    included,
    excluded,
    groups,
    readiness,
    counts: {
      selected: requested.length,
      loaded: files.length,
      compatible: included.length,
      excluded: excluded.length
    }
  }
}

function buildGroups(signatures: CompatibilitySignature[]): CompatibilityGroup[] {
  const groups = new Map<string, CompatibilityGroup>()
  for (const sig of signatures) {
    const key = groupKey(sig)
    const existing = groups.get(key)
    if (existing) existing.members.push(sig.msr)
    else groups.set(key, { key, members: [sig.msr], signature: sig })
  }
  return [...groups.values()]
}

/** Serialise a CanonicalSiteKey to the opaque string readiness/site maps key on.
 * (The extraction of CanonicalSiteKeys from rows is a later-task concern.) */
export const serializeSiteKey = (site: CanonicalSiteKey): string =>
  site.mp === null ? site.die : `${site.die}#${site.mp}`
