import { joinApiPath } from '~/utils/apiPath'

export type FailIssueToolType = 'cd-sem' | 'hv-sem'

export interface FailIssueSummary {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string | null
  end_date: string | null
  // Latest UTC date the backend has data for. Used as the date-picker's
  // anchor so "Last 7 days" presets don't overshoot the available window.
  anchor_date: string
  total_executions: number
  align_fail_count: number
  align_fail_rate: number
  align_na_count: number
  meas_fail_count: number
  meas_fail_rate: number
  // Echoed from the server — frontend reads it instead of hard-coding 15,
  // so a backend change to the threshold automatically updates UI copy.
  // Percent, 0..100, same scale as fail_ratio: 15 means 15%.
  meas_fail_threshold: number
  distinct_equipment: number
  distinct_recipes: number
  distinct_lots: number
}

export interface FailIssueDailyTrendPoint {
  date: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
}

export interface FailIssueDailyTrendResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  lot_cd: string | null
  points: FailIssueDailyTrendPoint[]
}

export interface FailIssueAlignRow {
  rank: number
  class_name: string
  recipe_name: string
  full_name: string
  exec_count: number
  align_fail_count: number
  align_fail_rate: number
  sample_eqp_ids: string[]
  fab_names: string[]
}

export interface FailIssueAlignRankingResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  limit: number
  lot_cd: string | null
  rows: FailIssueAlignRow[]
}

export interface FailIssueMeasRow {
  rank: number
  class_name: string
  recipe_name: string
  full_name: string
  exec_count: number
  meas_fail_count: number
  meas_fail_rate: number
  avg_fail_ratio: number
  sample_eqp_ids: string[]
  fab_names: string[]
}

export interface FailIssueMeasRankingResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  limit: number
  lot_cd: string | null
  rows: FailIssueMeasRow[]
}

export interface FailIssueDeviceRow {
  lot_cd: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
  prod_catg_cd: string | null
  tech_nm: string | null
}

export interface FailIssueDevicesResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  devices: FailIssueDeviceRow[]
}

export interface FailIssueQuery {
  toolType: FailIssueToolType
  fabNames?: string[]
  startDate?: string
  endDate?: string
  limit?: number
  lotCd?: string
}

const buildQuery = (params: FailIssueQuery) => {
  const query: Record<string, string> = {}
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.fabNames?.length) query.fab_name = params.fabNames.join(',')
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.lotCd) query.lot_cd = params.lotCd
  return query
}

// Path slug carries tool_type (unlike recipe-tat which serves both tools
// from /cdsem/...). Fail-issue keeps cdsem and hvsem as separate paths so
// the office swap can route the two indexes independently if needed.
const toolSlug = (toolType: FailIssueToolType): 'cdsem' | 'hvsem' =>
  toolType === 'hv-sem' ? 'hvsem' : 'cdsem'

export const useFailIssueApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchSummary = async (params: FailIssueQuery): Promise<FailIssueSummary> => {
    return await $fetch<FailIssueSummary>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/summary`),
      { query: buildQuery(params) }
    )
  }

  const fetchDailyTrend = async (
    params: FailIssueQuery
  ): Promise<FailIssueDailyTrendResponse> => {
    return await $fetch<FailIssueDailyTrendResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/daily-trend`),
      { query: buildQuery(params) }
    )
  }

  const fetchAlignRanking = async (
    params: FailIssueQuery
  ): Promise<FailIssueAlignRankingResponse> => {
    return await $fetch<FailIssueAlignRankingResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/align-ranking`),
      { query: buildQuery(params) }
    )
  }

  const fetchMeasRanking = async (
    params: FailIssueQuery
  ): Promise<FailIssueMeasRankingResponse> => {
    return await $fetch<FailIssueMeasRankingResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/meas-ranking`),
      { query: buildQuery(params) }
    )
  }

  const fetchDevices = async (
    params: FailIssueQuery
  ): Promise<FailIssueDevicesResponse> => {
    // /devices is scope-only — passing lot_cd would defeat its purpose
    // (this endpoint is the source of truth for which lot_cds exist).
    const scope: FailIssueQuery = {
      toolType: params.toolType,
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<FailIssueDevicesResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/devices`),
      { query: buildQuery(scope) }
    )
  }

  return {
    fetchSummary,
    fetchDailyTrend,
    fetchAlignRanking,
    fetchMeasRanking,
    fetchDevices
  }
}

// Format helpers
//
// Two formatters because the API carries two scales on purpose, and picking
// the wrong one is a silent 100x error that still renders as a believable
// percentage. Match the formatter to the field:
//
//   formatRate     — 0..1 fractions of ROWS: align_fail_rate, meas_fail_rate
//   formatPercent  — 0..100 image percentages: fail_ratio, avg_fail_ratio
//                    (already computed at that scale in OpenSearch)

export const formatRate = (value: number, fractionDigits = 2): string => {
  if (!Number.isFinite(value) || value <= 0) return '0%'
  return `${(value * 100).toFixed(fractionDigits)}%`
}

export const formatPercent = (value: number, fractionDigits = 2): string => {
  if (!Number.isFinite(value) || value <= 0) return '0%'
  return `${value.toFixed(fractionDigits)}%`
}
