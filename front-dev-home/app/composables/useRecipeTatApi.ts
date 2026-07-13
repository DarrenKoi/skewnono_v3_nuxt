import { joinApiPath } from '~/utils/apiPath'

export type RecipeTatToolType = 'cd-sem' | 'hv-sem'

export interface RecipeTatRow {
  rank: number
  class_name: string
  recipe_name: string
  full_name: string
  meas_counts: number
  total_meastime: number
  avg_meastime: number
  sample_lot_cds: string[]
  sample_eqp_ids: string[]
}

export interface RecipeTatRankingResponse {
  tool_type: RecipeTatToolType
  fab_id: string | null
  start_date: string
  end_date: string
  limit: number
  rows: RecipeTatRow[]
}

export interface RecipeTatSummary {
  tool_type: RecipeTatToolType
  fab_id: string | null
  start_date: string | null
  end_date: string | null
  // Latest UTC date for which the backend has data. The popover uses this
  // as its preset / max-value anchor so "Last 7 days" never overshoots the
  // available window.
  anchor_date: string
  total_tat_seconds: number
  total_recipes: number
  total_executions: number
  avg_meastime: number
}

export interface RecipeTatDailyTrendPoint {
  date: string
  total_meastime: number
  exec_count: number
}

export interface RecipeTatDailyTrendResponse {
  tool_type: RecipeTatToolType
  fab_id: string | null
  start_date: string
  end_date: string
  points: RecipeTatDailyTrendPoint[]
}

export interface RecipeTatDeviceRow {
  lot_cd: string
  exec_count: number
  total_meastime: number
  // Quick-filter metadata. R3 lots populate `prod_catg_cd`; M-fab lots
  // populate `tech_nm`. Exactly one of these is non-null per lot.
  prod_catg_cd: string | null
  tech_nm: string | null
}

export interface RecipeTatDevicesResponse {
  tool_type: RecipeTatToolType
  fab_id: string | null
  start_date: string
  end_date: string
  devices: RecipeTatDeviceRow[]
}

export interface RecipeTatQuery {
  toolType: RecipeTatToolType
  fabId?: string
  // Both bounds optional. When omitted, the backend defaults to the last
  // 30 days ending at its data-anchor date — clients should prefer that
  // over guessing wall-clock today, which can drift past the mock ceiling.
  startDate?: string
  endDate?: string
  limit?: number
  // 디바이스별 view passes a single lot_cd to scope ranking / summary /
  // daily-trend to one product device. Omit for the 전체 요약 view.
  lotCd?: string
}

const buildQuery = (params: RecipeTatQuery) => {
  const query: Record<string, string> = {
    tool_type: params.toolType
  }
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.fabId) query.fab_id = params.fabId
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.lotCd) query.lot_cd = params.lotCd
  return query
}

// Path-slug is the backend's source of truth for tool_type — see
// back_dev_home/ebeam/hitachi/_tool_specs.py's SLUG_TO_TOOL_TYPE.
// The ?tool_type= query param is informational and ignored by the route,
// so calling /cdsem/* from the HV-SEM page silently returns CD-SEM data.
const toolSlug = (toolType: RecipeTatToolType): 'cdsem' | 'hvsem' =>
  toolType === 'hv-sem' ? 'hvsem' : 'cdsem'

export const useRecipeTatApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeTatRanking = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatRankingResponse> => {
    return await $fetch<RecipeTatRankingResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/ranking`),
      { query: buildQuery(params) }
    )
  }

  const fetchRecipeTatSummary = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatSummary> => {
    return await $fetch<RecipeTatSummary>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/summary`),
      { query: buildQuery(params) }
    )
  }

  const fetchRecipeTatDailyTrend = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatDailyTrendResponse> => {
    return await $fetch<RecipeTatDailyTrendResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/daily-trend`),
      { query: buildQuery(params) }
    )
  }

  const fetchRecipeTatDevices = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatDevicesResponse> => {
    // /devices contract is scope-only — lot_cd would defeat its purpose
    // (this endpoint is the source of truth for which lot_cds exist) and
    // limit is ranking-specific. Strip both so callers can pass a wider
    // shared query object without polluting the request.
    const scope: RecipeTatQuery = {
      toolType: params.toolType,
      fabId: params.fabId,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<RecipeTatDevicesResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/devices`),
      { query: buildQuery(scope) }
    )
  }

  return {
    fetchRecipeTatRanking,
    fetchRecipeTatSummary,
    fetchRecipeTatDailyTrend,
    fetchRecipeTatDevices
  }
}

// Format helpers for display

export const formatSecondsAsDuration = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0s'
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`
  return `${s}s`
}

export const formatSecondsCompact = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`
  return `${(seconds / 3600).toFixed(2)}h`
}
