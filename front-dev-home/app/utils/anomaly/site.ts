// front-dev-home/app/utils/anomaly/site.ts
// Site-level abnormality: judge each measurement site against the OTHER sites on
// the same wafer, for one parameter.
//
// This is deliberately a thin adapter over peerVerdicts rather than a new
// algorithm. The app must have exactly one meaning for "outlier" — leave-one-out
// against peers, with `status` (did we evaluate?) held separate from `severity`
// (how bad?). An independent IQR-fence verdict living beside this one would let
// two panels disagree about the same site.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { MeasuredMsrRow } from '../msrRows.ts'
import { isMeasuredRow } from '../msrRows.ts'
import type { AnomalyVerdict, MethodConfig } from './types.ts'
import { DEFAULT_METHOD_CONFIG } from './types.ts'
import { peerVerdicts } from './peer.ts'

export interface SiteVerdict {
  row: MeasuredMsrRow
  verdict: AnomalyVerdict
}

export const siteVerdicts = (
  rows: MsrFileRow[],
  parameter: string,
  config: MethodConfig = DEFAULT_METHOD_CONFIG
): SiteVerdict[] => {
  // Gate FIRST. An unmeasured row admitted here would distort the peer band and
  // could mask a genuine outlier.
  const sites = rows.filter((r): r is MeasuredMsrRow => r.parameter === parameter && isMeasuredRow(r))
  if (sites.length === 0) return []

  const verdicts = peerVerdicts(sites.map(r => r.cd_value), {
    config,
    metric: 'site',
    tag: '사이트'
  })

  return sites.map((row, i) => ({ row, verdict: verdicts[i]! }))
}
