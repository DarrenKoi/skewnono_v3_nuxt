// Skewvoir analysis — grain-safe per-MSR feature table + provenance.
//
// One MsrFeatureRow per LOADED MsrFile, for the ACTIVE parameter. Time-Series
// (multi-point trend) and multi-MSR Correlation both read THIS table instead
// of recomputing their own level/spread/spatial numbers, so they can never
// disagree on what a given MSR's value is.
//
// Every exportable number is a DerivedValue<T>: value + unit + n (sample count
// used) + missing (excluded/nullable count) + transform (how it was computed)
// + reference (raw source field) + version (stable computation tag). This is
// what lets ANY chart/table trace a number back to raw data — see
// ProvenanceDrawer.vue, which renders exactly this shape.
//
// GRAIN SAFETY (the one thing this module must never get wrong): dynamic_fdc
// is captured PER SEQUENCE (dynamic_fdc[seq][param]). A sequence is not an
// independent MSR observation — it is one of several readings folded into a
// single measurement. So for each dynamic FDC param we reduce across
// sequences FIRST (mean/std/range/OLS slope vs sequence index/missing) and
// only THEN emit ONE MSR-level DerivedValue per param. "Robust slope" here
// uses `linearFit` (plain OLS) — no M-estimator is trivially available in
// utils/stats.ts, so this stays OLS; the transform string says so explicitly
// per Task 4's ambiguity resolution #2.
//
// health and spm_dict are BANNED here: health is a mock-only per-MSR
// abnormality scalar (useMsrFileApi.ts) and spm_dict is an explicitly-marked
// PLACEHOLDER parabola with no real signal. Nothing in this module reads
// `source.health` or `source.spm_dict`, and features.test.ts asserts neither
// name ever appears in a FeatureDefinition or on a feature row.
//
// DISPLAY-ONLY family `quality` (2026-10-09): the tool's own quality scores, the
// alignment offset and the time one point took. They are here so an engineer can
// LOOK at them beside CD; they are never judged. The research note excluded
// vendor scores from the judgement path
// (docs/issues/skewvoir/wafer-analysis-method-research.md §2, P0) because their
// meaning and calibration are unconfirmed, so nothing here thresholds them, and
// `qualityFeatures` takes neither the coverage counts nor the anomaly config —
// it cannot see a verdict. features.test.ts ("quality axes are display-only")
// pins both halves.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — every sibling import
// carries an explicit `.ts` extension.
import type { MsrFileRow, MsrParamSummary, FdcParamSummary, ExeDetailInfo, AlignmentInfo } from '~/composables/useMsrFileApi'
import { measuredRows, paramValues } from '../msrRows.ts'
import { mean, median, sampleStd, linearFit } from '../stats.ts'
import { overviewSites, type ParamCoverage } from '../overview.ts'
import { DEFAULT_METHOD_CONFIG, type MethodConfig } from '../anomaly/types.ts'
import { parseWaferGeometry, siteRadiusMm } from '../waferGeometry.ts'

// A stable tag for the computation formulas below. Bump it if any formula
// (mean/std/OLS/etc.) changes, so a persisted/exported DerivedValue can be
// recognised as stale.
const FEATURE_VERSION = 'msr-feature-v1'

// ── Public types ─────────────────────────────────────────────────────────

export type FeatureFamily
  = | 'level'
    | 'spread'
    | 'coverage'
    | 'failure'
    | 'spatial'
    | 'fixed_fdc'
    | 'dynamic_fdc'
    | 'quality'

// This table is exclusively MSR-grain: dynamic FDC's sequence grain is
// reduced away before a value ever reaches a feature (see module doc above).
export type FeatureGrain = 'msr'

/** Describes ONE column of the feature table — independent of any specific
 * MSR's data. `unit` reflects what the CURRENT data (active parameter, loaded
 * FDC params) actually carries, so a registry built from real sources never
 * invents a unit. */
export interface FeatureDefinition {
  id: string
  label: string
  unit: string
  grain: FeatureGrain
  source: string // raw source field(s), e.g. 'cd_value', 'dynamic_fdc.*.StigmaX'
  aggregation: string
  family: FeatureFamily
}

/** Every exportable derived number: traceable to its raw source and the exact
 * transform that produced it. */
export interface DerivedValue<T> {
  value: T
  unit: string
  n: number // sample count actually used
  missing: number // excluded/nullable count
  transform: string // human-readable "how computed"
  reference: string // raw source field
  version: string
}

/** A dynamic FDC param, reduced across sequences to one MSR-level summary.
 * `slope` is the OLS slope of value vs sequence index (units: param-unit per
 * sequence step). */
export interface DynamicFdcSummary {
  mean: number
  std: number
  range: number
  slope: number
}

/** One row per loaded MSR file, for one active parameter. */
export interface MsrFeatureRow {
  msr: string
  parameter: string
  level: DerivedValue<number>
  spread: DerivedValue<number>
  coverage: DerivedValue<number> // measured/total ratio
  failure: DerivedValue<number> // failed/total ratio
  // null when fewer than 2 measured (radius, value) pairs are available —
  // linearFit cannot fit a line through 0 or 1 point.
  spatial: DerivedValue<number> | null
  fixedFdc: Record<string, DerivedValue<number>>
  dynamicFdc: Record<string, DerivedValue<DynamicFdcSummary>>
  /** Display-only measurement-quality / execution signals, keyed by the axis id
   *  minus its `quality.` prefix. A key is ABSENT when this MSR has no figure. */
  quality: Record<string, DerivedValue<number>>
}

/** The one meas_hist fact a feature row needs — structural, so a
 *  `Map<msr, MeasHistRow>` passes as-is. */
export interface FeatureHistInput {
  meastime: number
}

// ── Input shape ──────────────────────────────────────────────────────────
// A structural subset of MsrFileResponse — deliberately does NOT include
// `health` or `spm_dict` (see module doc: banned). MsrFileResponse itself
// structurally satisfies this (it has these fields plus more), so callers can
// pass real API responses directly.
export interface FeatureSource {
  msr: string
  parameters: MsrParamSummary[]
  rows: MsrFileRow[]
  fixed_fdc: Record<string, number>
  dynamic_fdc: Record<string, Record<string, number>>
  fdc_params: FdcParamSummary[]
  exe_detail_info: ExeDetailInfo
  // Optional: a response can predate the field, and then there is simply no
  // alignment-offset figure.
  alignment?: Pick<AlignmentInfo, 'offset'>
}

// ── Helpers ──────────────────────────────────────────────────────────────

const isFinite = (v: number | undefined | null): v is number => v != null && Number.isFinite(v)

const paramUnit = (source: FeatureSource, parameter: string): string =>
  source.parameters.find(p => p.parameter === parameter)?.unit ?? ''

const firstParamUnit = (sources: FeatureSource[], parameter: string): string =>
  sources.map(s => paramUnit(s, parameter)).find(u => u) ?? ''

const fdcUnit = (sources: FeatureSource[], name: string): string => {
  for (const s of sources) {
    const u = s.fdc_params.find(p => p.name === name)?.unit
    if (u) return u
  }
  return ''
}

const dynamicFdcKeys = (source: FeatureSource): string[] => {
  const keys = new Set<string>()
  for (const perSeq of Object.values(source.dynamic_fdc)) {
    for (const k of Object.keys(perSeq)) keys.add(k)
  }
  return [...keys]
}

// ── Per-feature computation (row-level) ─────────────────────────────────

const levelFeature = (source: FeatureSource, parameter: string, cov: ParamCoverage): DerivedValue<number> => ({
  value: mean(paramValues(source.rows, parameter)),
  unit: paramUnit(source, parameter),
  n: cov.measured,
  missing: cov.failed,
  transform: 'mean of measured cd_value',
  reference: 'cd_value',
  version: FEATURE_VERSION
})

const spreadFeature = (source: FeatureSource, parameter: string, cov: ParamCoverage): DerivedValue<number> => ({
  value: sampleStd(paramValues(source.rows, parameter)),
  unit: paramUnit(source, parameter),
  n: cov.measured,
  missing: cov.failed,
  transform: 'sample std (n-1) of measured cd_value',
  reference: 'cd_value',
  version: FEATURE_VERSION
})

const coverageFeature = (cov: ParamCoverage): DerivedValue<number> => ({
  value: cov.total > 0 ? cov.measured / cov.total : Number.NaN,
  unit: 'ratio',
  n: cov.total,
  missing: cov.failed,
  transform: 'measured/total count ratio (utils/overview.ts overviewSites coverage)',
  reference: 'cd_value (isMeasuredRow gate)',
  version: FEATURE_VERSION
})

const failureFeature = (cov: ParamCoverage): DerivedValue<number> => ({
  value: cov.total > 0 ? cov.failed / cov.total : Number.NaN,
  unit: 'ratio',
  n: cov.total,
  missing: 0,
  transform: 'failed/total count ratio (cd_value null gate)',
  reference: 'cd_value (mp_number < 0 / cd_value null)',
  version: FEATURE_VERSION
})

// Centre -> edge spatial summary: fit cd_value against distance from wafer
// centre (siteRadiusMm) across the MEASURED sites for this parameter, then
// report the total predicted change from the innermost to outermost measured
// radius (slope * span) — in the parameter's own unit, not per-mm.
const spatialFeature = (source: FeatureSource, parameter: string): DerivedValue<number> | null => {
  const geo = parseWaferGeometry(source.exe_detail_info)
  const rows = measuredRows(source.rows.filter(r => r.parameter === parameter))
  const pairs: [number, number][] = []
  for (const r of rows) {
    const radius = siteRadiusMm(r.stage_coordinate, geo)
    if (radius != null) pairs.push([radius, r.cd_value])
  }
  const fit = linearFit(pairs)
  if (!fit) return null
  const radii = pairs.map(p => p[0])
  const span = Math.max(...radii) - Math.min(...radii)
  return {
    value: fit.slope * span,
    unit: paramUnit(source, parameter),
    n: pairs.length,
    missing: rows.length - pairs.length,
    transform: 'OLS linear fit (linearFit) of cd_value vs siteRadiusMm; delta = slope * (max radius - min radius) across measured sites',
    reference: 'stage_coordinate (siteRadiusMm) vs cd_value',
    version: FEATURE_VERSION
  }
}

// fixed_fdc is already ONE scalar per MSR — no reduction needed, n=1.
const fixedFdcFeatures = (source: FeatureSource): Record<string, DerivedValue<number>> => {
  const out: Record<string, DerivedValue<number>> = {}
  for (const [key, value] of Object.entries(source.fixed_fdc)) {
    out[key] = {
      value,
      unit: source.fdc_params.find(p => p.name === key)?.unit ?? '',
      n: 1,
      missing: 0,
      transform: 'fixed_fdc MSR-level scalar (already MSR grain; no reduction)',
      reference: `fixed_fdc.${key}`,
      version: FEATURE_VERSION
    }
  }
  return out
}

// dynamic_fdc is captured per sequence — reduce across sequences FIRST, then
// emit exactly ONE DerivedValue per param (see module doc: grain safety).
const dynamicFdcFeatures = (source: FeatureSource): Record<string, DerivedValue<DynamicFdcSummary>> => {
  const out: Record<string, DerivedValue<DynamicFdcSummary>> = {}
  const seqEntries = Object.entries(source.dynamic_fdc)
    .map(([seq, params]) => [Number(seq), params] as [number, Record<string, number>])
    .sort((a, b) => a[0] - b[0])

  for (const key of dynamicFdcKeys(source)) {
    const pairs: [number, number][] = []
    for (const [seq, params] of seqEntries) {
      const v = params[key]
      if (isFinite(v)) pairs.push([seq, v])
    }
    const values = pairs.map(p => p[1])
    const fit = linearFit(pairs)
    out[key] = {
      value: {
        mean: mean(values),
        std: sampleStd(values),
        range: values.length ? Math.max(...values) - Math.min(...values) : Number.NaN,
        slope: fit ? fit.slope : Number.NaN
      },
      unit: source.fdc_params.find(p => p.name === key)?.unit ?? '',
      n: values.length,
      missing: seqEntries.length - values.length,
      transform: 'sequence-grain reduction FIRST (mean/std/range/OLS slope [linearFit] of value vs sequence index), THEN one MSR-level entry — per-sequence points are never treated as independent MSR observations',
      reference: `dynamic_fdc.*.${key}`,
      version: FEATURE_VERSION
    }
  }
  return out
}

// ── Display-only: measurement quality / execution ───────────────────────

const SCORE_FIELDS = ['measurement_score', 'addressing1_score', 'addressing2_score'] as const

// '' and ' ' parse to 0 under Number(), which would draw a blank offset as a
// perfect one.
const strictNumber = (text: string | undefined): number | null => {
  if (text == null || text.trim() === '') return null
  const n = Number(text)
  return Number.isFinite(n) ? n : null
}

const alignmentKeys = (source: FeatureSource): string[] => Object.keys(source.alignment?.offset ?? {})

const qualityFeatures = (
  source: FeatureSource,
  parameter: string,
  hist: FeatureHistInput | undefined
): Record<string, DerivedValue<number>> => {
  const out: Record<string, DerivedValue<number>> = {}
  const rows = source.rows.filter(r => r.parameter === parameter)

  // Median over EVERY row of the active parameter that carries a score —
  // deliberately not `measuredRows`: a failed measurement's score is the one an
  // engineer most wants to see, so the cd_value gate must not drop it. Rows with
  // no score are counted in `missing`.
  // OFFICE-VERIFY: the score scale and direction are not stated in
  // docs/datatables/hitachi/msr_file_pickle.txt (examples only: "165", "868",
  // "None"), so the unit stays '' and nothing ranks a score as good or bad.
  for (const field of SCORE_FIELDS) {
    const values = rows.map(r => r[field]).filter(isFinite)
    if (!values.length) continue
    out[field] = {
      value: median(values),
      unit: '',
      n: values.length,
      missing: rows.length - values.length,
      transform: `median of ${field} over the active parameter's rows that carry a score (failed rows included)`,
      reference: field,
      version: FEATURE_VERSION
    }
  }

  // One figure PER alignment point: points differ in method (OM / SEM), so
  // folding them into one number would mix stages nobody said are comparable.
  // OFFICE-VERIFY: the offset unit is not stated in the schema of record, and
  // whether elements 1 and 2 are x and y is taken from the example
  // `["OM", "365", "3525", ..]` alone.
  for (const [key, entry] of Object.entries(source.alignment?.offset ?? {})) {
    const x = strictNumber(entry[1])
    const y = strictNumber(entry[2])
    if (x == null || y == null) continue
    out[`alignment_offset.${key}`] = {
      value: Math.hypot(x, y),
      unit: '',
      n: 1,
      missing: 0,
      transform: 'hypot of the two offset components (elements 1 and 2 of the entry)',
      reference: `alignment.offset.${key}`,
      version: FEATURE_VERSION
    }
  }

  // meastime is seconds and is 0 when the document carries none
  // (docs/datatables/hitachi/meas_hist.txt), so 0 means "no figure", not "instant".
  const sequences = new Set(source.rows.map(r => r.sequence)).size
  if (hist && hist.meastime > 0 && sequences > 0) {
    out.sec_per_point = {
      value: hist.meastime / sequences,
      unit: 's',
      n: sequences,
      missing: 0,
      transform: 'meas_hist meastime / distinct sequences in the MSR',
      reference: 'meastime, sequence',
      version: FEATURE_VERSION
    }
  }
  return out
}

// ── Public API ───────────────────────────────────────────────────────────

/** One MsrFeatureRow per source, for the active parameter. Sources are
 * deduped by msr (first occurrence wins) so a caller can safely pass
 * [focusFile, ...setFiles.values()] without pre-filtering. */
export const featureRows = (
  sources: FeatureSource[],
  parameter: string,
  config: MethodConfig = DEFAULT_METHOD_CONFIG,
  hist: ReadonlyMap<string, FeatureHistInput> = new Map()
): MsrFeatureRow[] => {
  const seen = new Set<string>()
  const out: MsrFeatureRow[] = []
  for (const source of sources) {
    if (seen.has(source.msr)) continue
    seen.add(source.msr)

    const ov = overviewSites(source.rows, parameter, config)
    out.push({
      msr: source.msr,
      parameter,
      level: levelFeature(source, parameter, ov.coverage),
      spread: spreadFeature(source, parameter, ov.coverage),
      coverage: coverageFeature(ov.coverage),
      failure: failureFeature(ov.coverage),
      spatial: spatialFeature(source, parameter),
      fixedFdc: fixedFdcFeatures(source),
      dynamicFdc: dynamicFdcFeatures(source),
      quality: qualityFeatures(source, parameter, hist.get(source.msr))
    })
  }
  return out
}

/** The column dictionary for the CURRENT sources + active parameter — every
 * fixed/dynamic FDC key that appears in ANY of the sources gets one entry,
 * with unit resolved from the first source that carries it. Units are never
 * combined across parameters/FDC of different unit (no 'total'/'combined'
 * entry exists here — every feature keeps its own unit). */
export const featureRegistry = (
  sources: FeatureSource[],
  parameter: string
): FeatureDefinition[] => {
  const unit = firstParamUnit(sources, parameter)

  const defs: FeatureDefinition[] = [
    { id: 'level', label: `${parameter} 평균`, unit, grain: 'msr', source: 'cd_value', aggregation: 'mean of measured cd_value', family: 'level' },
    { id: 'spread', label: `${parameter} 산포`, unit, grain: 'msr', source: 'cd_value', aggregation: 'sample std (n-1) of measured cd_value', family: 'spread' },
    { id: 'coverage', label: '측정 커버리지', unit: 'ratio', grain: 'msr', source: 'cd_value', aggregation: 'measured/total count ratio', family: 'coverage' },
    { id: 'failure', label: '측정 실패율', unit: 'ratio', grain: 'msr', source: 'cd_value', aggregation: 'failed/total count ratio', family: 'failure' },
    { id: 'spatial', label: `${parameter} 중심→외곽 변화량`, unit, grain: 'msr', source: 'stage_coordinate,cd_value', aggregation: 'OLS slope * radius span (linearFit over siteRadiusMm)', family: 'spatial' }
  ]

  const fixedKeys = new Set<string>()
  for (const s of sources) for (const k of Object.keys(s.fixed_fdc)) fixedKeys.add(k)
  for (const key of fixedKeys) {
    defs.push({
      id: `fixed_fdc.${key}`,
      label: key,
      unit: fdcUnit(sources, key),
      grain: 'msr',
      source: `fixed_fdc.${key}`,
      aggregation: 'MSR-level scalar (already MSR grain; no reduction)',
      family: 'fixed_fdc'
    })
  }

  const dynamicKeys = new Set<string>()
  for (const s of sources) for (const key of dynamicFdcKeys(s)) dynamicKeys.add(key)
  for (const key of dynamicKeys) {
    defs.push({
      id: `dynamic_fdc.${key}`,
      label: key,
      unit: fdcUnit(sources, key),
      grain: 'msr',
      source: `dynamic_fdc.*.${key}`,
      aggregation: 'sequence-grain mean/std/range/OLS-slope reduced to one MSR-level entry',
      family: 'dynamic_fdc'
    })
  }

  // Display-only quality / execution axes — last, so they never become a
  // default axis. Units: only `s` is stated by the schema of record.
  for (const field of SCORE_FIELDS) {
    defs.push({ id: `quality.${field}`, label: `${field} 중앙값`, unit: '', grain: 'msr', source: field, aggregation: 'median over the active parameter rows that carry a score (failed rows included)', family: 'quality' })
  }
  defs.push({ id: 'quality.sec_per_point', label: '측정점당 소요 시간', unit: 's', grain: 'msr', source: 'meastime,sequence', aggregation: 'meastime / distinct sequences', family: 'quality' })
  for (const key of new Set(sources.flatMap(alignmentKeys))) {
    defs.push({ id: `quality.alignment_offset.${key}`, label: `alignment offset ${key} 크기`, unit: '', grain: 'msr', source: `alignment.offset.${key}`, aggregation: 'hypot of the two offset components', family: 'quality' })
  }

  return defs
}
