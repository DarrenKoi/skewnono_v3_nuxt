// front-dev-home/app/utils/anomaly/score.ts
// Two interchangeable scoring methods that band a value's distance from a center.
// Both return the same ScorePart shape so any comparison base can use either.
import type { RangeConfig, Severity, StddevConfig } from './types.ts'

export interface ScorePart {
  status: 'evaluated' | 'insufficient'
  severity: Severity
  score: number
  reason: string
}

const r = (n: number, d = 2): number => Number(n.toFixed(d))
const sgn = (n: number): string => (n >= 0 ? '+' : '')

const INSUFFICIENT: ScorePart = {
  status: 'insufficient', severity: 'normal', score: NaN, reason: '표본 부족 — 미평가'
}

export const bandRange = (absDevPct: number, cfg: RangeConfig): Severity =>
  absDevPct < cfg.watchPct ? 'normal' : absDevPct < cfg.abnormalPct ? 'watch' : 'abnormal'

export const bandStddev = (absK: number, cfg: StddevConfig): Severity =>
  absK < cfg.watchK ? 'normal' : absK < cfg.abnormalK ? 'watch' : 'abnormal'

// Range (authoritative): % deviation from a LOO center. `tag` is a Korean prefix
// for the reason (e.g. '산포' for the spread metric); empty for the mean metric.
export const scoreByRange = (
  value: number, center: number, cfg: RangeConfig, tag = ''
): ScorePart => {
  if (!Number.isFinite(value) || !Number.isFinite(center) || Math.abs(center) < cfg.minAbsCenter) {
    return INSUFFICIENT
  }
  const devPct = ((value - center) / Math.abs(center)) * 100
  const severity = bandRange(Math.abs(devPct), cfg)
  const pre = tag ? `${tag} ` : ''
  const exceed = severity === 'normal' ? '' : ' 초과'
  const reason = `${pre}나머지 평균 ${r(center)} 대비 ${sgn(devPct)}${r(devPct, 1)}% (실측 ${r(value)}) · 허용 ±${cfg.watchPct}%${exceed}`
  return { status: 'evaluated', severity, score: devPct, reason }
}

// Stddev (diagnostic): classic (value − mean) / std against a LOO center.
export const scoreByStddev = (
  value: number, mean: number, std: number, cfg: StddevConfig, tag = ''
): ScorePart => {
  if (!Number.isFinite(value) || !Number.isFinite(mean) || !Number.isFinite(std)) {
    return INSUFFICIENT
  }
  const pre = tag ? `${tag} ` : ''
  if (std === 0) {
    if (value === mean) {
      return { status: 'evaluated', severity: 'normal', score: 0, reason: `${pre}나머지 동일값, 편차 없음` }
    }
    const delta = value - mean
    return {
      status: 'evaluated', severity: 'abnormal', score: delta,
      reason: `${pre}표준편차 0 기준에서 이탈, Δ ${sgn(delta)}${r(delta)}`
    }
  }
  const k = (value - mean) / std
  const severity = bandStddev(Math.abs(k), cfg)
  const exceed = severity === 'normal' ? '' : ` · ±${cfg.abnormalK}σ 초과`
  const reason = `${pre}나머지 평균 ${r(mean)}, 표준편차 ${r(std)} · ${sgn(k)}${r(k)}σ (실측 ${r(value)})${exceed}`
  return { status: 'evaluated', severity, score: k, reason }
}
