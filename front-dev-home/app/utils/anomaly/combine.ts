// Reduce several signals on one item to a single CombinedVerdict.
// worst-of severity over EVALUATED verdicts only; insufficient ones are kept in
// the array (so "a detector couldn't run" survives, not buried under normal).
import type { AnomalyVerdict, CombinedVerdict, Severity } from './types.ts'

const RANK: Record<Severity, number> = { normal: 0, watch: 1, abnormal: 2 }

export const combineVerdicts = (verdicts: AnomalyVerdict[]): CombinedVerdict => {
  const sorted = [...verdicts].sort((a, b) => {
    if (a.status !== b.status) return a.status === 'evaluated' ? -1 : 1
    const dr = RANK[b.severity] - RANK[a.severity]
    if (dr !== 0) return dr
    const sa = Number.isFinite(a.score) ? Math.abs(a.score) : -1
    const sb = Number.isFinite(b.score) ? Math.abs(b.score) : -1
    return sb - sa
  })

  const evaluated = verdicts.filter(v => v.status === 'evaluated')
  if (evaluated.length === 0) {
    return { status: 'insufficient', severity: 'normal', verdicts: sorted }
  }
  const severity = evaluated.reduce<Severity>(
    (worst, v) => (RANK[v.severity] > RANK[worst] ? v.severity : worst),
    'normal'
  )
  return { status: 'evaluated', severity, verdicts: sorted }
}
