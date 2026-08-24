// front-dev-home/app/utils/anomaly/peer.ts
// Peer comparison base: judge each value against the LEAVE-ONE-OUT mean of the
// others (and, for stddev, their LOO sample std). LOO is what prevents an
// outlier from inflating its own band and masking itself.
import type { AnomalyVerdict, MethodConfig } from './types.ts'
import { PEER_MIN_N } from './types.ts'
import { scoreByRange, scoreByStddev } from './score.ts'

export interface PeerOptions {
  config: MethodConfig
  metric: string // 'mean' | 'spread'
  tag?: string // Korean reason prefix, e.g. '산포'
  minN?: number
}

export interface PeerVerdict extends AnomalyVerdict {
  /** Leave-one-out reference centre and spread used for this verdict. */
  peerMean: number | null
  peerStd: number | null
}

// Mean + sample std (n-1) of all finite entries except index `skip`.
const looStats = (values: number[], skip: number): { mean: number, std: number } | null => {
  const others: number[] = []
  for (let i = 0; i < values.length; i++) {
    if (i === skip) continue
    const v = values[i]!
    if (Number.isFinite(v)) others.push(v)
  }
  if (others.length < 1) return null
  const mean = others.reduce((s, v) => s + v, 0) / others.length
  const std = others.length > 1
    ? Math.sqrt(others.reduce((s, v) => s + (v - mean) ** 2, 0) / (others.length - 1))
    : 0
  return { mean, std }
}

export const peerVerdicts = (values: number[], opts: PeerOptions): PeerVerdict[] => {
  const { config, metric, tag = '' } = opts
  const method = config.method
  const minN = opts.minN ?? PEER_MIN_N[method]

  const insufficient = (): PeerVerdict => ({
    status: 'insufficient', severity: 'normal', method, score: NaN,
    reason: '표본 부족 — 미평가', metric, signal: 'peer',
    peerMean: null, peerStd: null
  })

  // Re-check N after dropping non-finite values (Codex #8): too few real points → none evaluated.
  const finiteCount = values.filter(Number.isFinite).length
  if (finiteCount < minN) return values.map(insufficient)

  return values.map((value, i) => {
    if (!Number.isFinite(value)) return insufficient()
    const stats = looStats(values, i)
    if (!stats) return insufficient()
    const part = method === 'range'
      ? scoreByRange(value, stats.mean, config.range, tag)
      : scoreByStddev(value, stats.mean, stats.std, config.stddev, tag)
    return {
      ...part,
      method,
      metric,
      signal: 'peer' as const,
      peerMean: stats.mean,
      peerStd: stats.std
    }
  })
}
