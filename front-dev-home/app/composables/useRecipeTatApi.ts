import { joinApiPath } from '~/utils/apiPath'
import type { SEM_TOOL_TYPES } from '~/utils/toolType'

// recipe-tat is Hitachi-only (back_dev_home/ebeam/recipe_tat) — no
// AMAT adapter exists or is planned, so this stays narrower than the full
// ToolType registry on purpose. @deprecated name kept for call sites.
export type RecipeTatToolType = (typeof SEM_TOOL_TYPES)[number]

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
  fab_names: string[]
}

export interface RecipeTatRankingResponse {
  tool_type: RecipeTatToolType
  fab_names: string[]
  start_date: string
  end_date: string
  // Echo of the requested cap. 0 means uncapped — the backend returned every
  // recipe in the date range (the default; views no longer send a limit).
  limit: number
  rows: RecipeTatRow[]
}

export interface RecipeTatSummary {
  tool_type: RecipeTatToolType
  fab_names: string[]
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
  fab_names: string[]
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
  fab_names: string[]
  start_date: string
  end_date: string
  devices: RecipeTatDeviceRow[]
}

export interface RecipeTatEquipmentRow {
  eqp_id: string
  fab_name: string
  eqp_model_cd: string
  // 표시용. 신호 판정에는 쓰지 않습니다 — 가동률은 "얼마나 바빴는가"이지
  // "몇 번 돌았는가"가 아닙니다.
  exec_count: number
  total_meastime: number
  avg_meastime: number
  recipe_count: number
  top_recipe: string | null
  top_recipe_share: number
  // 실제 총 TAT / 이 장비의 레시피 구성이면 걸렸어야 할 TAT.
  // 표본 미달이면 null.
  tat_index: number | null
  // 측정 점유율. MES 가동률이 아닙니다 — 로딩·대기·PM이 빠져 있습니다.
  occupancy: number
  usage_ratio: number
}

export interface RecipeTatFleetReference {
  tool_count: number
  total_executions: number
  total_meastime: number
  window_seconds: number
  median_total_meastime: number
  median_recipe_count: number
  min_sample: number
  percentiles: Record<string, Record<string, number>>
}

export interface RecipeTatEquipmentsResponse {
  tool_type: RecipeTatToolType
  fab_names: string[]
  start_date: string | null
  end_date: string | null
  fleet: RecipeTatFleetReference
  equipments: RecipeTatEquipmentRow[]
}

export interface RecipeTatEquipmentTrendSeries {
  eqp_id: string
  points: RecipeTatDailyTrendPoint[]
}

export interface RecipeTatEquipmentRecipeCell {
  eqp_id: string
  meas_counts: number
  total_meastime: number
  avg_meastime: number
}

export interface RecipeTatEquipmentRecipeRow {
  class_name: string
  recipe_name: string
  full_name: string
  total_meastime: number
  // 선택 장비 수만큼, 요청 순서 그대로. 미실행 장비는 0으로 채워집니다.
  cells: RecipeTatEquipmentRecipeCell[]
}

export interface RecipeTatEquipmentCompareResponse {
  tool_type: RecipeTatToolType
  fab_names: string[]
  start_date: string | null
  end_date: string | null
  // 실제로 사용된 목록(상한 적용 후). 요청보다 짧으면 절단된 것입니다.
  eqp_ids: string[]
  trends: RecipeTatEquipmentTrendSeries[]
  recipes: RecipeTatEquipmentRecipeRow[]
}

export interface RecipeTatQuery {
  toolType: RecipeTatToolType
  fabNames?: string[]
  // Both bounds optional. When omitted, the backend defaults to the last
  // 14 days ending at its data-anchor date — clients should prefer that
  // over guessing wall-clock today, which can drift past the mock ceiling.
  startDate?: string
  endDate?: string
  limit?: number
  // 디바이스별 view passes a single lot_cd to scope ranking / summary /
  // daily-trend to one product device. Omit for the 전체 요약 view.
  lotCd?: string
  // 장비별 비교 뷰가 최대 MAX_COMPARE_EQPS 대를 쉼표로 보냅니다.
  eqpIds?: string[]
}

const buildQuery = (params: RecipeTatQuery) => {
  const query: Record<string, string> = {
    tool_type: params.toolType
  }
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.fabNames?.length) query.fab_name = params.fabNames.join(',')
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.lotCd) query.lot_cd = params.lotCd
  if (params.eqpIds?.length) query.eqp_id = params.eqpIds.join(',')
  return query
}

// Path-slug is the backend's source of truth for tool_type — see
// back_dev_home/ebeam/_tool_specs.py's SLUG_TO_TOOL_TYPE.
// The ?tool_type= query param is informational and ignored by the route,
// so calling /cdsem/* from the HV-SEM page silently returns CD-SEM data.
// toolSlug now comes from ~/utils/toolType via Nuxt auto-import.

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
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<RecipeTatDevicesResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/devices`),
      { query: buildQuery(scope) }
    )
  }

  const fetchRecipeTatEquipments = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatEquipmentsResponse> => {
    // /devices 와 같은 이유로 lot_cd·limit 을 벗겨냅니다: 이 엔드포인트는
    // 범위 안에 어떤 장비가 있는지에 대한 진실이라 선택으로 걸러지면
    // 안 됩니다.
    const scope: RecipeTatQuery = {
      toolType: params.toolType,
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<RecipeTatEquipmentsResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/equipments`),
      { query: buildQuery(scope) }
    )
  }

  const fetchRecipeTatEquipmentCompare = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatEquipmentCompareResponse> => {
    return await $fetch<RecipeTatEquipmentCompareResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/equipment-compare`),
      { query: buildQuery(params) }
    )
  }

  return {
    fetchRecipeTatRanking,
    fetchRecipeTatSummary,
    fetchRecipeTatDailyTrend,
    fetchRecipeTatDevices,
    fetchRecipeTatEquipments,
    fetchRecipeTatEquipmentCompare
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
