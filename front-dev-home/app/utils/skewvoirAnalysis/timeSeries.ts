// Skewvoir Time-Series — derivations for the multi-measurement (set) lenses.
//
// Every function here is pure so it runs under raw `node --test`; the composable
// only wires them to reactive state and the .vue files only render.
//
// A TrendPoint carries BOTH raw statistics and display values:
//   mean / min / max   — always as measured
//   value / bandLo/Hi  — what the chart plots, after the baseline is applied
//
// That split is load-bearing, not redundancy. The `range` scoring method divides
// by the leave-one-out center, so judging baseline-shifted values would change
// every percentage. Anomaly verdicts and tool skew read the RAW fields.
import type { TsAxisMode, TsBaseline } from './types.ts'
import type { MsrParamSummary } from '~/composables/useMsrFileApi'
import { quantileSorted, mean as meanOf, sampleStd } from '../stats.ts'
import { peerVerdicts, combineVerdicts, type MethodConfig, type CombinedVerdict } from '../anomaly/index.ts'
import { isNamedParam } from './paramOrder.ts'

/** The meas_hist facts a trend point needs. Structural (not MeasHistRow) so the
 *  tests can build one without a 25-field fixture. */
export interface TrendRowInput {
  msr: string
  /** Presentation label, built by the caller (`eqp_id · timestamp`). */
  label: string
  eqpId: string
  timestamp: string
}

/** The MsrFile facts a trend point needs. */
export interface TrendFileInput {
  parameters: MsrParamSummary[]
}

export interface TrendPoint {
  msr: string
  label: string
  eqpId: string
  /** Epoch ms, or null when the timestamp could not be parsed. */
  ts: number | null
  // Raw statistics — never baseline-shifted.
  mean: number
  min: number
  max: number
  std: number
  // Display values — baseline applied.
  value: number
  bandLo: number
  bandHi: number
  /** Absent ONLY for an unnamed settling MP. With too few peers the verdict is
   *  still present, carrying status 'insufficient' — peerVerdicts returns an
   *  insufficient verdict rather than nothing, and the chart renders that as
   *  the grey 판정 불가 tone. */
  verdict?: CombinedVerdict
}

export interface BuildTrendOptions {
  baseline: TsBaseline
  config: MethodConfig
}

/** Median of the set's measurement means — the `세트 기준`.
 *
 *  Sorts defensively: quantileSorted indexes without sorting (its contract says
 *  "caller pre-sorts"), so an unsorted caller gets a confident wrong number. */
export const setBaseline = (means: number[]): number => {
  const sorted = means.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return Number.NaN
  return quantileSorted(sorted, 0.5)
}

const parseTs = (timestamp: string): number | null => {
  const t = new Date(timestamp).getTime()
  return Number.isFinite(t) ? t : null
}

export const buildTrendSeries = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, TrendFileInput>,
  parameter: string,
  opts: BuildTrendOptions
): TrendPoint[] => {
  const raw: TrendPoint[] = []
  for (const row of rows) {
    const summary = files.get(row.msr)?.parameters.find(p => p.parameter === parameter)
    if (!summary) continue
    raw.push({
      msr: row.msr,
      label: row.label,
      eqpId: row.eqpId,
      ts: parseTs(row.timestamp),
      mean: summary.mean,
      min: summary.min,
      max: summary.max,
      std: summary.std,
      // Overwritten below once the baseline is known.
      value: summary.mean,
      bandLo: summary.min,
      bandHi: summary.max
    })
  }

  // Chronological, with unparseable timestamps held at the end in authored
  // order rather than dropped — they are still real measurements, and the
  // `order` axis can show them honestly.
  raw.sort((a, b) => {
    if (a.ts == null && b.ts == null) return 0
    if (a.ts == null) return 1
    if (b.ts == null) return -1
    return a.ts - b.ts
  })

  const base = opts.baseline === 'resid' ? setBaseline(raw.map(p => p.mean)) : 0
  const shift = Number.isFinite(base) ? base : 0
  const points = raw.map(p => ({
    ...p,
    value: p.mean - shift,
    bandLo: p.min - shift,
    bandHi: p.max - shift
  }))

  // No peer judgement on an unnamed settling MP: comparing one measurement's
  // warm-up shot against another's says nothing about either wafer.
  if (!isNamedParam(parameter)) return points

  // Judged on RAW means, so the verdicts are identical in raw and residual mode.
  const meanV = peerVerdicts(points.map(p => p.mean), { config: opts.config, metric: 'mean' })
  const spreadV = peerVerdicts(points.map(p => p.std), { config: opts.config, metric: 'spread', tag: '산포' })
  return points.map((p, i) => ({ ...p, verdict: combineVerdicts([meanV[i]!, spreadV[i]!]) }))
}

/** A trend point paired with the x value it is drawn at. */
export interface PlacedTrendPoint {
  p: TrendPoint
  /** Epoch ms under a `time` axis; the point's index under `order`; the tool's
   *  index into `distinctEqpIds` under `eqp`. */
  x: number
}

/** The category-axis labels for `eqp` mode, in a deterministic order (sorted by
 *  id). BOTH the chart's axis data and placeTrendPoints index into this same
 *  list, so a point can never land under another tool's label. */
export const distinctEqpIds = (points: readonly TrendPoint[]): string[] =>
  [...new Set(points.map(p => p.eqpId))].sort((a, b) => a.localeCompare(b))

/** The points the trend chart can actually position, in plot order.
 *
 *  A measurement whose timestamp would not parse has NO position on a time
 *  axis, so the `time` branch drops it. `order` plots by index, which every
 *  point has, so it drops nothing — an unparseable timestamp is still a real
 *  measurement and the order axis can show it honestly. `eqp` places every
 *  point on its tool's column (each point has an eqpId), so it also drops
 *  nothing.
 *
 *  Under `order` the x is the index into the FULL array, so it lines up with a
 *  category axis whose `data` is built from every point; under `eqp` it is the
 *  index into `distinctEqpIds`, the same list the axis renders.
 *
 *  Exported rather than kept inside the chart component so a panel can report
 *  what the chart hid — `points.length - placeTrendPoints(points, mode).length`
 *  — without reaching into the component for it. */
export const placeTrendPoints = (
  points: readonly TrendPoint[],
  axisMode: TsAxisMode
): PlacedTrendPoint[] => {
  if (axisMode === 'eqp') {
    const eqps = distinctEqpIds(points)
    return points.map(p => ({ p, x: eqps.indexOf(p.eqpId) }))
  }
  return points
    .map((p, i) => ({ p, x: axisMode === 'time' ? p.ts : i }))
    .filter((e): e is PlacedTrendPoint => e.x != null)
}

/** The site facts the distribution lens needs.
 *
 *  Deliberately a MINIMAL structural type, not `MsrFileRow`. `MsrFileRow` has
 *  ~20 required fields (coordinates, image names, measurement conditions,
 *  scores); demanding it here would force every test fixture to invent all of
 *  them. `nuxt typecheck` covers `app/**` INCLUDING `*.test.ts`, so a shortcut
 *  fixture would not merely be untidy — it would fail the build. A real
 *  MsrFileRow still satisfies this shape structurally. */
export interface DistSiteInput {
  parameter: string
  mp_number: number
  cd_value: number | null
}

export interface DistFileInput {
  rows: DistSiteInput[]
}

/** Local mirror of utils/msrRows.ts's isMeasuredRow, narrowed to DistSiteInput.
 *  Same rule — mp_number < 0 is a metadata-only point with no measurement, and
 *  a null cd_value is the contract for "no data" — but it does not demand a
 *  full MsrFileRow. Keep the two in sync. */
const isMeasuredSite = (r: DistSiteInput): r is DistSiteInput & { cd_value: number } =>
  r.mp_number >= 0 && r.cd_value != null && Number.isFinite(r.cd_value)

/** Matches DistributionChart.vue's `DistributionGroup` prop shape. */
export interface SetDistributionGroup {
  label: string
  values: number[]
}

/** One box per measurement, from the site rows already in setFiles.
 *
 *  A measurement with no measured site is dropped rather than contributed as an
 *  empty box — the caller reports the count in the panel meta. */
export const buildSetDistributionGroups = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, DistFileInput>,
  parameter: string
): SetDistributionGroup[] => {
  const groups: SetDistributionGroup[] = []
  for (const row of rows) {
    const file = files.get(row.msr)
    if (!file) continue
    const values: number[] = []
    for (const site of file.rows) {
      if (site.parameter === parameter && isMeasuredSite(site)) values.push(site.cd_value)
    }
    if (values.length === 0) continue
    groups.push({ label: row.label, values })
  }
  return groups
}

export interface ToolSkewRow {
  eqpId: string
  /** Measurements this tool contributed to the set. */
  n: number
  /** Mean of this tool's measurement means (raw). */
  mean: number
  /** mean - 세트 기준. */
  offset: number
  /** Sample std across this tool's means; null when n < 2 (not estimable). */
  sigma: number | null
}

/** Distinct equipment in the set. The panel needs this to tell "one tool"
 *  (say 단일 장비) apart from "no data" (say nothing) — buildToolSkew returns an
 *  empty array for both. */
export const distinctToolCount = (points: readonly TrendPoint[]): number =>
  new Set(points.map(p => p.eqpId)).size

/** Per-equipment offset from the set baseline.
 *
 *  Reads the RAW `mean`, so the rows are identical in raw and residual mode —
 *  an offset is already a delta. No verdict or status is produced: with a
 *  hand-picked set spanning recipes, an offset is not attributable enough to
 *  grade.
 *
 *  A single-tool set yields NO rows. Its baseline is that tool's own median, so
 *  the "offset" would be a number about nothing — a row reading ≈0 invites the
 *  conclusion that the tool agrees with its peers when it has none. */
export const buildToolSkew = (
  points: readonly TrendPoint[],
  baseline: number
): ToolSkewRow[] => {
  if (distinctToolCount(points) < 2) return []

  const byTool = new Map<string, number[]>()
  for (const p of points) {
    const list = byTool.get(p.eqpId)
    if (list) list.push(p.mean)
    else byTool.set(p.eqpId, [p.mean])
  }

  const rows: ToolSkewRow[] = []
  for (const [eqpId, means] of byTool) {
    const m = meanOf(means)
    rows.push({
      eqpId,
      n: means.length,
      mean: m,
      offset: m - baseline,
      sigma: means.length > 1 ? sampleStd(means) : null
    })
  }

  rows.sort((a, b) => Math.abs(b.offset) - Math.abs(a.offset))
  return rows
}

/** The MsrFile facts the parameter selector needs: which parameters exist, and
 *  the MP order rows that break coverage ties. */
export interface OptionFileInput {
  parameters: MsrParamSummary[]
  rows: { parameter: string, mp_number: number, sequence: number }[]
}

export interface SetParamOption {
  parameter: string
  /** Measurements in the set whose file carries this parameter. */
  covered: number
  /** Measurements whose file loaded at all — the coverage denominator. */
  loaded: number
}

/** Set-aware parameter list with coverage.
 *
 *  NOT `ParamCoverage` — utils/overview.ts already owns that name for
 *  attempted/measured/failed SITES within one measurement.
 *
 *  Ordering must be deterministic across a heterogeneous set. sortByRowMpOrder
 *  answers "what order are one measurement's parameters in", and recipes can
 *  disagree, so the set uses: coverage desc → lowest (mp_number, sequence) in
 *  the set → name. */
export const setParamOptions = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, OptionFileInput>
): SetParamOption[] => {
  const covered = new Map<string, number>()
  const rank = new Map<string, [number, number]>()
  let loaded = 0

  for (const row of rows) {
    const file = files.get(row.msr)
    if (!file) continue
    loaded++
    for (const p of file.parameters) {
      covered.set(p.parameter, (covered.get(p.parameter) ?? 0) + 1)
    }
    for (const r of file.rows) {
      if (r.mp_number < 0) continue
      const current = rank.get(r.parameter)
      if (!current || r.mp_number < current[0] || (r.mp_number === current[0] && r.sequence < current[1])) {
        rank.set(r.parameter, [r.mp_number, r.sequence])
      }
    }
  }

  const options = [...covered].map(([parameter, n]) => ({ parameter, covered: n, loaded }))
  const NO_RANK: [number, number] = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY]
  options.sort((a, b) => {
    if (b.covered !== a.covered) return b.covered - a.covered
    const ra = rank.get(a.parameter) ?? NO_RANK
    const rb = rank.get(b.parameter) ?? NO_RANK
    if (ra[0] !== rb[0]) return ra[0] - rb[0]
    if (ra[1] !== rb[1]) return ra[1] - rb[1]
    return a.parameter.localeCompare(b.parameter)
  })
  return options
}

/** A resolved set row plus the recipe, for the confounding badge. */
export interface IntegrityRowInput extends TrendRowInput {
  recipeName: string
}

export interface SetIntegrity {
  /** Ids in the URL `msrs`. */
  requested: number
  /** Ids that matched a measurement-history row. Since the analysis resolves
   *  against BOTH SEM families' histories, an unresolved id means a stale or
   *  hand-edited link, not a cross-family pick. */
  resolved: number
  /** Resolved measurements whose MsrFile actually came back. */
  loaded: number
  /** Distinct recipes in the set. >1 means tool skew is confounded. */
  recipeCount: number
}

export const setIntegrity = (
  msrList: readonly string[],
  resolvedRows: readonly IntegrityRowInput[],
  files: ReadonlyMap<string, unknown>
): SetIntegrity => ({
  requested: msrList.length,
  resolved: resolvedRows.length,
  loaded: resolvedRows.filter(r => files.has(r.msr)).length,
  recipeCount: new Set(resolvedRows.map(r => r.recipeName)).size
})

/** The site facts one Sequence Trend line needs. `sequence` on top of the
 *  distribution lens's fields, because the x axis IS the sequence. */
export interface SeqSiteInput extends DistSiteInput {
  sequence: number
}

export interface SeqFileInput {
  rows: SeqSiteInput[]
}

/** One Sequence Trend line per measurement in the set. */
export interface SequenceGroup {
  msr: string
  label: string
  eqpId: string
  /** [sequence, cd_value] in sequence order. */
  points: [number, number][]
}

/** Every loaded measurement's internal sequence for one parameter, so the
 *  Sequence Trend can overlay the whole set (one line per measurement, colored
 *  by tool) instead of showing the focus alone. A measurement with no measured
 *  site for the parameter contributes no line — same drop rule as the
 *  distribution lens. */
export const buildSequenceSeries = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, SeqFileInput>,
  parameter: string
): SequenceGroup[] => {
  const groups: SequenceGroup[] = []
  for (const row of rows) {
    const file = files.get(row.msr)
    if (!file) continue
    const points: [number, number][] = []
    for (const site of file.rows) {
      if (site.parameter === parameter && isMeasuredSite(site)) {
        points.push([site.sequence, site.cd_value])
      }
    }
    if (points.length === 0) continue
    points.sort((a, b) => a[0] - b[0])
    groups.push({ msr: row.msr, label: row.label, eqpId: row.eqpId, points })
  }
  return groups
}
