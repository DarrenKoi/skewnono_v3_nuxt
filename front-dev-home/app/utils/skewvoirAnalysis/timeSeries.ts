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
import type { TsBaseline } from './types.ts'
import type { MsrParamSummary } from '~/composables/useMsrFileApi'
import { quantileSorted } from '../stats.ts'
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
