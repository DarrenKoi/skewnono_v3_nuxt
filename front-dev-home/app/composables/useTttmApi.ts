import { joinApiPath } from '~/utils/apiPath'
import type { SkewMatrix, Confidence, Tier } from '~/utils/tttmGrouping'

export interface ToolRef { eqp_id: string, label: string }

export interface SkewCondition {
  cell_id: string
  beam_condition: string
  axis: 'X' | 'Y'
  cd_band: string
  mdc_epoch: string
  tier: Tier
  confidence: Confidence
  labels: string[]
  direct_skew_matrix: SkewMatrix | null
  predicted_skew_matrix: SkewMatrix | null
}

export interface ProductionCorroboration {
  level: 'high' | 'mid' | 'low'
  note: string
  detail: { pair: string, overlap: number }[]
}

export interface FleetToday {
  matrix: SkewMatrix
  consensus_deviation: { eqp_id: string, deviation: number }[]
}

export interface TrendPoint { eqp_id: string, date: string, skew: number }
export interface EpochMarker {
  eqp_id: string
  date: string
  kind: 'hard' | 'soft'
  mdc_changed: boolean
  label: string
}
export interface MdcHistoryEntry {
  eqp_id: string
  beam_condition: string
  axis: 'X' | 'Y'
  date: string
  old_value: number
  new_value: number
}

export interface TttmCheckPayload {
  tool_slug: string
  fab_name: string
  recipe_id: string | null
  available: boolean
  fetched_at: string
  summary: string
  tools: ToolRef[]
  current_tolerance: number
  tolerance_range: { min: number, max: number, step: number }
  occupied_cells: SkewCondition[]
  production_corroboration: ProductionCorroboration
  fleet_today: FleetToday
  trend: TrendPoint[]
  epoch_markers: EpochMarker[]
  mdc_history: MdcHistoryEntry[]
}

// Frontend tool-type 'cd-sem' maps to backend tool_slug 'cdsem'.
const toSlug = (toolType: string) => toolType.replace('-', '')

export const useTttmApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchTttmCheck = (toolType: string, fabName: string, recipeId?: string) =>
    $fetch<TttmCheckPayload>(
      joinApiPath(base, `/${toSlug(toolType)}/tttm/check`),
      { query: { fab_name: fabName, ...(recipeId ? { recipe_id: recipeId } : {}) } }
    )

  const useTttmCheck = (toolType: string, fabName: string, recipeId?: string) =>
    useAsyncData(
      `tttm-check:${toolType}:${fabName}:${recipeId ?? 'all'}`,
      () => fetchTttmCheck(toolType, fabName, recipeId)
    )

  return { fetchTttmCheck, useTttmCheck }
}
