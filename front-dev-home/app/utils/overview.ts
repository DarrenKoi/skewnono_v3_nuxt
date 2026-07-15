// front-dev-home/app/utils/overview.ts
// Pure B1 (측정 개요) analytics for ONE parameter: coverage, site outlier count,
// evaluation status, and the flagged/failed rows for the 이상·실패 사이트 table.
//
// This is the single source every overview panel renders, so the verdict strip,
// the navigator's OUT column, the wafer ◎ rings, and the site table can never
// disagree. "Outlier" here is exactly siteVerdicts (leave-one-out) — no second
// definition — and failures (cd_value: null) are a separate axis that never
// enters the outlier count or the statistics.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { EvalStatus, MethodConfig } from './anomaly/types.ts'
import { DEFAULT_METHOD_CONFIG } from './anomaly/types.ts'
import { siteVerdicts } from './anomaly/site.ts'
import { isMeasuredRow } from './msrRows.ts'

export interface ParamCoverage {
  total: number    // rows attempted for this parameter
  measured: number // rows with a real cd_value
  failed: number   // total - measured (cd_value: null)
}

export type SiteKind = 'abnormal' | 'watch' | 'failed'

export interface OverviewSiteRow {
  sequence: number
  chip: string          // chip_number, e.g. '-4, 6'
  cd: number | null     // null for a failed site
  delta: number | null  // signed % vs sibling sites (range method); null for failed
  kind: SiteKind
}

export interface OverviewSites {
  coverage: ParamCoverage
  outlierCount: number // sites with severity abnormal|watch (evaluated only)
  status: EvalStatus   // 'insufficient' when too few measured sites to judge
  tableRows: OverviewSiteRow[] // flagged + failed, sorted for the table
}

const KIND_RANK: Record<SiteKind, number> = { abnormal: 0, watch: 1, failed: 2 }

export const overviewSites = (
  rows: MsrFileRow[],
  parameter: string,
  config: MethodConfig = DEFAULT_METHOD_CONFIG
): OverviewSites => {
  const forParam = rows.filter(r => r.parameter === parameter)
  const measured = forParam.filter(isMeasuredRow)
  const coverage: ParamCoverage = {
    total: forParam.length,
    measured: measured.length,
    failed: forParam.length - measured.length
  }

  const verdicts = siteVerdicts(rows, parameter, config)
  // siteVerdicts assigns one shared status across the pool (peer-based), so the
  // first verdict's status represents the whole parameter. Empty → insufficient.
  const status: EvalStatus = verdicts[0]?.verdict.status ?? 'insufficient'

  const flagged: OverviewSiteRow[] = verdicts
    .filter(v => v.verdict.status === 'evaluated'
      && (v.verdict.severity === 'abnormal' || v.verdict.severity === 'watch'))
    .map(v => ({
      sequence: v.row.sequence,
      chip: v.row.chip_number,
      cd: v.row.cd_value,
      delta: v.verdict.score,
      kind: v.verdict.severity as 'abnormal' | 'watch'
    }))

  const failed: OverviewSiteRow[] = forParam
    .filter(r => !isMeasuredRow(r))
    .map(r => ({ sequence: r.sequence, chip: r.chip_number, cd: null, delta: null, kind: 'failed' as const }))

  const tableRows = [...flagged, ...failed].sort((a, b) => {
    if (KIND_RANK[a.kind] !== KIND_RANK[b.kind]) return KIND_RANK[a.kind] - KIND_RANK[b.kind]
    if (a.kind === 'failed') return a.sequence - b.sequence
    return Math.abs(b.delta!) - Math.abs(a.delta!) // larger deviation first
  })

  return { coverage, outlierCount: flagged.length, status, tableRows }
}
