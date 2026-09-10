// Shared abnormality-detection contract. Pure types + defaults, no framework deps.
// status and severity are SEPARATE axes: status = "did detection run?",
// severity = "how abnormal?" (only meaningful when evaluated).

export type EvalStatus = 'evaluated' | 'insufficient'
export type Severity = 'normal' | 'watch' | 'abnormal'
export type ScoringMethod = 'range' | 'stddev'
export type AnomalySignal = 'peer' | 'sibling' | 'recent-shift'

export interface AnomalyVerdict {
  status: EvalStatus
  severity: Severity // valid only when status === 'evaluated'
  method: ScoringMethod // decides the unit of `score`
  score: number // range → signed % deviation; stddev → signed σ (NaN when insufficient)
  reason: string // Korean, value-bearing
  metric: string // 'mean' | 'spread' | ...
  signal: AnomalySignal
}

export interface CombinedVerdict {
  status: EvalStatus
  severity: Severity
  verdicts: AnomalyVerdict[]
}

export interface RangeConfig {
  watchPct: number
  abnormalPct: number
  minAbsCenter: number // |center| below this → insufficient (zero-centred metric guard)
}
export interface StddevConfig {
  watchK: number
  abnormalK: number
}
export interface MethodConfig {
  method: ScoringMethod
  range: RangeConfig
  stddev: StddevConfig
}

export const DEFAULT_RANGE: RangeConfig = { watchPct: 10, abnormalPct: 20, minAbsCenter: 1e-6 }
export const DEFAULT_STDDEV: StddevConfig = { watchK: 2, abnormalK: 3 }
export const DEFAULT_METHOD_CONFIG: MethodConfig = {
  method: 'range',
  range: DEFAULT_RANGE,
  stddev: DEFAULT_STDDEV
}

// Effective minimum sample size per method (stddev needs more to estimate spread).
export const PEER_MIN_N: Record<ScoringMethod, number> = { range: 3, stddev: 5 }
