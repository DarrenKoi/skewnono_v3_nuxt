// Skewvoir analysis — truth types for cross-MSR compatibility.
//
// These types are the KEYSTONE the spatial / sequence / relationship / gallery /
// hand-off tasks build on. The single governing rule is UNKNOWN-SAFE:
// a field is either KNOWN (extracted from the response and trustworthy) or
// UNKNOWN (not carried by the current data). Two signatures are equal on a field
// ONLY when both sides are known and equal — `unknown` is NEVER equal to
// `unknown`, and a single representative value is NEVER invented where the data
// actually holds several. This is what gates the office-only readiness (multi-MSR
// delta, site variability, same-site gallery) to `unavailable` in Phase-1 mock.

// ── Unknown-safe field wrappers ────────────────────────────────────────────

/** A value that is present and trustworthy. */
export interface Known<T> {
  state: 'known'
  value: T
}

/** A value the current data does not carry. Never fabricated, never equal to
 * another unknown. */
export interface Unknown {
  state: 'unknown'
}

export type Maybe<T> = Known<T> | Unknown

/** A per-row-varying acquisition field reduced across one MSR's rows:
 * - `single`  — every measured row agrees on one value.
 * - `mixed`   — the rows genuinely hold several distinct values.
 * - `unknown` — no measured row carried a usable value.
 * Two MSRs match on such a field only when BOTH are `single` and equal. */
export type FieldSet<T>
  = | { state: 'single', value: T }
    | { state: 'mixed', values: T[] }
    | { state: 'unknown' }

// ── Signature ──────────────────────────────────────────────────────────────

export interface RecipeIdentity {
  recipeName: string
  idpName: Maybe<string>
  idwName: Maybe<string>
}

export interface CoordinateMetadata {
  waferSize: Maybe<string>
  chipArray: Maybe<string>
  chipPitch: Maybe<string>
  mapOffset: Maybe<string>
  mapOrigin: Maybe<string>
}

/** The comparable fingerprint of one MSR, taken relative to a chosen analysis
 * parameter. Everything here is unknown-safe. */
export interface CompatibilitySignature {
  msr: string
  parameter: string
  // Recipe identity — KNOWN from exe_detail_info.
  recipe: Maybe<RecipeIdentity>
  // Office-gated: absent in Phase-1 mock → always unknown here.
  recipeRevision: Maybe<string>
  // Parameter unit — KNOWN from the parameter summary.
  unit: Maybe<string>
  // Per-row-varying acquisition context — reduced to a set, never averaged.
  measMethod: FieldSet<string>
  objectType: FieldSet<string>
  measKind: FieldSet<string>
  mag: FieldSet<number>
  vac: FieldSet<number>
  pixel: FieldSet<string>
  // Coordinate metadata — KNOWN from exe_detail_info.
  coordinate: CoordinateMetadata
  // Office-gated site-layout identity: absent in Phase-1 mock → always unknown.
  // The gate for multi-MSR delta / site variability / same-site gallery.
  siteLayoutHash: Maybe<string>
}

export type AnalysisScope = 'single' | 'set'

// ── Exclusion + grouping ────────────────────────────────────────────────────

/** Distinct reason codes for why a loaded MSR is not compatible with the focus.
 * `layout-mismatch` is a KNOWN conflict of hashes; an unknown layout is NOT an
 * exclusion (it only downgrades layout-dependent readiness). */
export type ExclusionReason
  = | 'recipe-mismatch'
    | 'layout-mismatch'
    | 'unit-mismatch'
    | 'method-mismatch'
    | 'metadata-missing'

export interface ExclusionEntry {
  msr: string
  reasons: ExclusionReason[]
}

/** A cluster of mutually-compatible MSRs sharing a signature key. */
export interface CompatibilityGroup {
  key: string
  members: string[]
  signature: CompatibilitySignature
}

// ── Readiness ────────────────────────────────────────────────────────────────

export interface Readiness {
  status: 'ready' | 'limited' | 'unavailable'
  reasons: string[]
}

export interface ReadinessMatrix {
  // Centre→edge / MSR-to-MSR delta needs a shared physical layout.
  multiMsrDelta: Readiness
  // Site-to-site variability across the set needs a shared physical layout.
  siteVariability: Readiness
  // Browsing the same physical site across MSRs needs a shared physical layout.
  sameSiteGallery: Readiness
}

// ── Manifest ─────────────────────────────────────────────────────────────────

export interface ManifestCounts {
  selected: number
  loaded: number
  compatible: number
  excluded: number
}

export interface AnalysisManifest {
  scope: AnalysisScope
  parameter: string
  focus: string
  // MSRs the user selected (may exceed `loaded` if some failed to load).
  requested: string[]
  // MSRs whose file actually loaded.
  loaded: string[]
  // Loaded MSRs compatible with the focus (the focus is always included).
  included: string[]
  // Loaded MSRs excluded from the analysis, each with distinct reason codes.
  excluded: ExclusionEntry[]
  groups: CompatibilityGroup[]
  readiness: ReadinessMatrix
  counts: ManifestCounts
}

// ── Types consumed by later tasks (definitions only) ─────────────────────────

/** A layout-independent identity for a physical measurement site, so the same
 * site can be recognised across MSRs. Consumed by the spatial / gallery tasks;
 * its extraction algorithm is out of scope here. */
export interface CanonicalSiteKey {
  // Die index within the wafer array (chip_number "col,row").
  die: string
  // Measurement-point index within the die, when point-level identity is needed.
  mp: number | null
}

/** The focus MSR described as the reference every candidate is compared against.
 * Consumed by the spatial / sequence / hand-off tasks. */
export interface ReferenceDescriptor {
  msr: string
  parameter: string
  scope: AnalysisScope
  signature: CompatibilitySignature
}

/** Which rule produced the sequence axis of a single-MSR FDC model.
 *
 * `param` — the ACTIVE PARAMETER's own measurement rows. `sequence` is a global
 * running counter over the whole MSR, so a parameter owns an interleaved subset
 * of it; scoping to that subset is what keeps a CD point and the FDC point
 * beside it describing the SAME measurement.
 *
 * `all` — every sequence in the MSR, including other parameters' measurements.
 * Answers "what did the tool do BETWEEN my points", at the cost of a CD line
 * that is mostly gaps. */
export type SequenceAxisMode = 'param' | 'all'
