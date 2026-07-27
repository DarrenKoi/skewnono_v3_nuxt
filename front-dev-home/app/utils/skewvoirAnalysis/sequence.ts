// Skewvoir single-MSR measurement-order (sequence) workbench.
//
// ONE MSR, ONE parameter, measured in a fixed order. This module describes how
// the CD and the per-sequence dynamic FDC evolve ALONG THE MEASUREMENT ORDER —
// the sequence index — and nothing else. It is the data layer behind the
// Time-Series `single` scope (SequenceWorkbench.vue).
//
// TIME IS NOT A DIMENSION HERE. The Phase-1 MsrFile carries NO per-sequence
// timestamp (docs/datatables/msr_file_pickle.txt), so this module deliberately exposes
// no per-second rate and no time lag — every slope is value-per-SEQUENCE-STEP
// and every unit label ends with "per sequence". sequence.test.ts pins this:
// any per-second / time-lag output would be a fabricated number.
//
// AXIS: by default the sequence axis is the ACTIVE PARAMETER's own measurement
// rows. `sequence` is a global running counter over the whole MSR — one number
// per row, consecutive numbers belonging to DIFFERENT parameters — so a
// parameter owns an interleaved subset and `dynamic_fdc` always holds strictly
// more entries than the CD axis. Pass axisMode 'all' for the whole-MSR union.
//
// CD ↔ dynamic-FDC coupling is DEMO-ONLY: the home mock biases both by a single
// per-MSR `health` scalar (useMsrFileApi.ts), so any apparent correlation is not
// method-validated. That caveat is surfaced by the component (pane meta), not
// invented here; this module just aligns the two on a shared sequence axis.
//
// REUSE, do not re-derive:
//   • utils/msrRows.ts — isMeasuredRow (the measured↔failure gate)
//   • utils/stats.ts   — linearFit (OLS slope vs sequence index)
//
// "Robust slope": utils/stats.ts offers no M-estimator, so — exactly as
// features.ts settled — the slope is plain OLS (linearFit) of value vs the
// sequence index. It is honest about the grain (per sequence), not about being
// outlier-resistant.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { MsrFileRow, FdcParamSummary, FdcCategory } from '~/composables/useMsrFileApi'
import type { SequenceAxisMode } from './types.ts'
import { isMeasuredRow } from '../msrRows.ts'
import { linearFit } from '../stats.ts'

// Re-exported so consumers have one import surface for the axis-mode type.
export type { SequenceAxisMode } from './types.ts'

// ── Public types ───────────────────────────────────────────────────────────

/** One point of a value series, indexed by measurement-order sequence.
 * `value` is null when the point was not measured (a failure or a metadata-only
 * point), so a gap in the line is honest rather than interpolated. */
export interface SeqPoint {
  sequence: number
  value: number | null
  measured: boolean
}

/** Start / end / range / slope / missing over the SEQUENCE. `slope` is the OLS
 * slope of value vs sequence index (value per sequence step); `slopeUnit` always
 * ends with "per sequence" — never a per-second rate. */
export interface SeqStats {
  start: number // first measured value (NaN when none measured)
  end: number // last measured value
  range: number // max - min over measured values
  slope: number // OLS slope vs sequence index; NaN when < 2 measured points
  missing: number // count of non-measured points on the axis
  n: number // measured point count
  unit: string
  slopeUnit: string // `${unit} per sequence` (or 'per sequence' when unitless)
}

/** A per-sequence dynamic-FDC pane: one FDC param traced across sequences,
 * aligned onto the shared sequence axis (missing sequences → null). */
export interface FdcSeqSeries {
  param: string
  category: FdcCategory
  unit: string
  nominal: number
  points: SeqPoint[]
  stats: SeqStats
}

/** Evidence markers for one sequence, for the event lane. */
export interface SeqEvent {
  sequence: number
  chip: string
  failure: boolean // the parameter row exists but was not measured (cd null)
  image: boolean // the point carries at least one SEM image
  alignment: boolean // the point carries addressing/alignment scores
}

/** The §Invariant check: one row is one measurement and `dynamic_fdc` holds
 * that measurement's tool state, so the two counts must agree. Reported rather
 * than absorbed — a mismatch means the data is wrong, not that the axis should
 * quietly cope. */
export interface SequenceIntegrity {
  rows: number
  fdc: number
  matched: boolean
}

/** The shared-cursor sequence model for one focus MSR + active parameter. */
export interface SequenceModel {
  parameter: string
  unit: string
  /** The shared cursor axis: every sequence CD and FDC panes index. Sorted. */
  sequences: number[]
  cd: { points: SeqPoint[], stats: SeqStats }
  fdc: FdcSeqSeries[]
  hasFdc: boolean
  fdcReason: string | null
  events: SeqEvent[]
  /** sequence → chip (chip_number), so moving the cursor can set focusedSite. */
  siteBySequence: Record<number, string>
  /** Which rule produced `sequences`. */
  axisMode: SequenceAxisMode
  /** dynamic_fdc sequences that fell OFF the axis — other parameters'
   * measurements. Always 0 when axisMode is 'all'. */
  excludedFdc: number
  /** len(rows) vs len(dynamic_fdc). See SequenceIntegrity. */
  integrity: SequenceIntegrity
}

// Structural subset of MsrFileResponse — accepts a real API response directly.
export interface SequenceSource {
  rows: MsrFileRow[]
  dynamic_fdc: Record<string, Record<string, number>>
  fdc_params: FdcParamSummary[]
}

// ── Helpers ────────────────────────────────────────────────────────────────

const slopeUnitLabel = (unit: string): string =>
  unit ? `${unit} per sequence` : 'per sequence'

// Reduce a sequence→value series (nulls allowed) to start/end/range/slope/missing.
/** Project a value series onto the shared sequence axis: one slot per sequence,
 * null where the point is absent or was not measured. Owned here because both
 * the per-pane charts and the matrix model need the identical rule, and a gap
 * must never be interpolated into a measurement. */
export const alignToSequences = (
  points: SeqPoint[],
  sequences: number[]
): (number | null)[] => {
  const bySeq = new Map(points.map(p => [p.sequence, p.measured ? p.value : null]))
  return sequences.map(s => bySeq.get(s) ?? null)
}

const statsOf = (points: SeqPoint[], unit: string): SeqStats => {
  const measured = points.filter((p): p is SeqPoint & { value: number } =>
    p.measured && p.value != null && Number.isFinite(p.value))
  const values = measured.map(p => p.value)
  const fit = linearFit(measured.map(p => [p.sequence, p.value]))
  return {
    start: values.length ? values[0]! : Number.NaN,
    end: values.length ? values[values.length - 1]! : Number.NaN,
    range: values.length ? Math.max(...values) - Math.min(...values) : Number.NaN,
    slope: fit ? fit.slope : Number.NaN,
    missing: points.length - measured.length,
    n: measured.length,
    unit,
    slopeUnit: slopeUnitLabel(unit)
  }
}

const hasImage = (r: MsrFileRow): boolean =>
  (r.no_of_mp_image ?? 0) > 0 || (r.mp_image_name_01 ?? '') !== ''

const hasAlignment = (r: MsrFileRow): boolean =>
  r.addressing1_score != null || r.addressing2_score != null

// ── Public API ─────────────────────────────────────────────────────────────

/** Build the shared-cursor sequence model for the focus MSR + active parameter.
 * `unit` is the parameter's CD unit (activeUnit). */
export const analyzeSequence = (
  source: SequenceSource,
  parameter: string,
  unit: string,
  axisMode: SequenceAxisMode = 'param'
): SequenceModel => {
  // CD rows for the active parameter, in measurement order.
  const cdRows = source.rows
    .filter(r => r.parameter === parameter)
    .sort((a, b) => a.sequence - b.sequence)

  const cdPoints: SeqPoint[] = cdRows.map(r => ({
    sequence: r.sequence,
    value: isMeasuredRow(r) ? r.cd_value : null,
    measured: isMeasuredRow(r)
  }))

  const siteBySequence: Record<number, string> = {}
  for (const r of cdRows) siteBySequence[r.sequence] = r.chip_number

  // Dynamic-FDC sequence keys (numeric) present in the file.
  const fdcSeqEntries = Object.entries(source.dynamic_fdc)
    .map(([seq, params]) => [Number(seq), params] as [number, Record<string, number>])
    .filter(([seq]) => Number.isFinite(seq))
    .sort((a, b) => a[0] - b[0])

  // The shared cursor axis.
  //
  // 'param' — the ACTIVE PARAMETER's own rows, and nothing else. `sequence` is a
  // global counter over the whole MSR with consecutive numbers belonging to
  // DIFFERENT parameters, so the old union-with-dynamic_fdc axis plotted other
  // parameters' measurements in every FDC pane and computed each pane's stats
  // over the whole MSR under a parameter-scoped heading.
  // 'all' — the union, kept verbatim so the opt-out is a real comparison.
  const axis = new Set<number>()
  for (const r of cdRows) axis.add(r.sequence)
  if (axisMode === 'all') {
    for (const [seq] of fdcSeqEntries) axis.add(seq)
  }
  const sequences = [...axis].sort((a, b) => a - b)

  // FDC entries that fall off the axis belong to other parameters' measurements.
  const onAxis = fdcSeqEntries.filter(([seq]) => axis.has(seq))
  const excludedFdc = fdcSeqEntries.length - onAxis.length

  // Which dynamic FDC params appear ON THE AXIS. Deriving this from every
  // sequence instead would render an all-null pane for a param that was only
  // sampled during another parameter's measurements.
  const fdcKeys = new Set<string>()
  for (const [, params] of onAxis) {
    for (const k of Object.keys(params)) fdcKeys.add(k)
  }

  const fdcBySeq = new Map(onAxis)
  const summaryOf = (name: string): FdcParamSummary | undefined =>
    source.fdc_params.find(p => p.name === name)

  const fdc: FdcSeqSeries[] = [...fdcKeys].map((name) => {
    const summary = summaryOf(name)
    const points: SeqPoint[] = sequences.map((seq) => {
      const v = fdcBySeq.get(seq)?.[name]
      const measured = v != null && Number.isFinite(v)
      return { sequence: seq, value: measured ? v : null, measured }
    })
    const fdcUnit = summary?.unit ?? ''
    return {
      param: name,
      category: summary?.category ?? 'source',
      unit: fdcUnit,
      nominal: summary?.nominal ?? Number.NaN,
      points,
      stats: statsOf(points, fdcUnit)
    }
  }).sort((a, b) => a.param.localeCompare(b.param))

  // Event lane — one entry per CD-row sequence, flags for the three evidence
  // kinds. Only CD rows carry image/alignment/failure metadata.
  const events: SeqEvent[] = cdRows.map(r => ({
    sequence: r.sequence,
    chip: r.chip_number,
    failure: !isMeasuredRow(r),
    image: hasImage(r),
    alignment: hasAlignment(r)
  }))

  const hasFdc = fdc.length > 0
  const fdcReason = hasFdc
    ? null
    : '이 측정에는 sequence별 dynamic FDC 데이터가 없습니다.'

  const fdcCount = Object.keys(source.dynamic_fdc).length
  const integrity: SequenceIntegrity = {
    rows: source.rows.length,
    fdc: fdcCount,
    matched: source.rows.length === fdcCount
  }

  return {
    parameter,
    unit,
    sequences,
    cd: { points: cdPoints, stats: statsOf(cdPoints, unit) },
    fdc,
    hasFdc,
    fdcReason,
    events,
    siteBySequence,
    axisMode,
    excludedFdc,
    integrity
  }
}
