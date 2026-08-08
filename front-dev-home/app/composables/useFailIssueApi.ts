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

export interface FailIssueEquipmentRow {
  eqp_id: string
  fab_name: string
  eqp_model_cd: string
  exec_count: number
  align_fail_count: number
  align_fail_rate: number
  // 이 장비의 레시피 구성이면 나왔어야 할 실패 건수. 지수 툴팁이 씁니다.
  align_expected: number
  // actual / expected. 표시 하한 미만이면 null — "실패하지 않았다"가 아니라
  // "모른다"입니다. 정렬에서도 0 으로 취급하면 안 됩니다.
  align_index: number | null
  align_index_low: number | null
  align_index_high: number | null
  meas_fail_count: number
  meas_fail_rate: number
  meas_expected: number
  meas_index: number | null
  meas_index_low: number | null
  meas_index_high: number | null
  recipe_count: number
  top_recipe: string | null
  top_recipe_share: number
}

export interface FailIssueFleetReference {
  tool_count: number
  total_executions: number
  align_fail_count: number
  meas_fail_count: number
  align_fail_rate: number
  meas_fail_rate: number
  median_exec_count: number
  median_recipe_count: number
  min_expected_fails: number
  confidence_z: number
  percentiles: Record<string, Record<string, number>>
}

export interface FailIssueEquipmentsResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  fleet: FailIssueFleetReference
  equipments: FailIssueEquipmentRow[]
}

export interface FailIssueEquipmentTrendPoint {
  date: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
}

export interface FailIssueEquipmentTrendSeries {
  eqp_id: string
  points: FailIssueEquipmentTrendPoint[]
}

export interface FailIssueEquipmentRecipeCell {
  eqp_id: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
}

export interface FailIssueEquipmentRecipeRow {
  class_name: string
  recipe_name: string
  full_name: string
  total_exec_count: number
  total_align_fail_count: number
  total_meas_fail_count: number
  // 응답의 eqp_ids 와 같은 순서·같은 길이입니다. 백엔드가 0채움을 보장하므로
  // 인덱스로 바로 꽂아도 됩니다.
  cells: FailIssueEquipmentRecipeCell[]
}

export interface FailIssueEquipmentCompareResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  eqp_ids: string[]
  trends: FailIssueEquipmentTrendSeries[]
  recipes: FailIssueEquipmentRecipeRow[]
}

export interface FailIssueQuery {
  toolType: FailIssueToolType
  fabNames?: string[]
  startDate?: string
  endDate?: string
  limit?: number
  lotCd?: string
  eqpIds?: string[]
}

const buildQuery = (params: FailIssueQuery) => {
  const query: Record<string, string> = {}
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.fabNames?.length) query.fab_name = params.fabNames.join(',')
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.lotCd) query.lot_cd = params.lotCd
  if (params.eqpIds?.length) query.eqp_id = params.eqpIds.join(',')
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

  const fetchEquipments = async (
    params: FailIssueQuery
  ): Promise<FailIssueEquipmentsResponse> => {
    // /devices 와 같이 scope 전용입니다 — lot_cd 나 eqp_id 를 넘기면 "범위
    // 안에 어떤 장비가 있는가"라는 이 엔드포인트의 목적이 무너집니다.
    const scope: FailIssueQuery = {
      toolType: params.toolType,
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<FailIssueEquipmentsResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/equipments`),
      { query: buildQuery(scope) }
    )
  }

  const fetchEquipmentCompare = async (
    params: FailIssueQuery
  ): Promise<FailIssueEquipmentCompareResponse> => {
    return await $fetch<FailIssueEquipmentCompareResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/equipment-compare`),
      { query: buildQuery(params) }
    )
  }

  return {
    fetchSummary,
    fetchDailyTrend,
    fetchAlignRanking,
    fetchMeasRanking,
    fetchDevices,
    fetchEquipments,
    fetchEquipmentCompare
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
