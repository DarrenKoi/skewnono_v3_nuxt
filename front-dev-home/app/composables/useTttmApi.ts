import { joinApiPath } from '~/utils/apiPath'
import type { SkewMatrix, Confidence, Tier } from '~/utils/tttmGrouping'

// `eqp_model_cd` is the raw sem_list model code (CG6300, TP4500, …). The fleet
// picker groups its chips by it — see utils/tttmToolGroups.
export interface ToolRef { eqp_id: string, label: string, eqp_model_cd: string }

export interface SkewCondition {
  cell_id: string
  beam_condition: string
  axis: 'X' | 'Y'
  cd_band: string
  /** Median measured CD (nm) behind this cell; null when none came back. */
  median_cd_nm: number | null
  mdc_epoch: string
  tier: Tier
  confidence: Confidence
  labels: string[]
  direct_skew_matrix: SkewMatrix | null
  predicted_skew_matrix: SkewMatrix | null
}

/**
 * The matrix a cell should be read through: measured beats modelled.
 *
 * Both tiers are independently nullable, so the preference order is a rule and
 * not a formality. It was stated twice with different null handling — a `!`
 * assertion in PairMatrix and a filter in TttmView — which is one definition
 * too many for a rule that decides which numbers the screen shows.
 */
export const preferredMatrix = (cell: SkewCondition): SkewMatrix | null =>
  cell.direct_skew_matrix ?? cell.predicted_skew_matrix

export interface ProductionCorroboration {
  level: 'high' | 'mid' | 'low'
  note: string
  detail: { pair: string, overlap: number }[]
}

export interface FleetToday {
  matrix: SkewMatrix
  consensus_deviation: { eqp_id: string, deviation: number }[]
  /** Median measured CD (nm) behind today's fleet numbers; null when unknown. */
  median_cd_nm: number | null
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
  /** The one measured feature these numbers are about; null = all folded. */
  parameter: string | null
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

  // `parameter` is only sent alongside a recipe: the server answers 400 to a
  // parameter on its own, because the same parameter name in another recipe
  // measures a different feature. Dropping it here rather than letting the
  // request fail keeps a stale stored parameter from breaking the page while
  // the user has no recipe picked.
  const fetchTttmCheck = (
    toolType: string,
    fabName: string,
    recipeId?: string,
    parameter?: string
  ) =>
    $fetch<TttmCheckPayload>(
      joinApiPath(base, `/${toSlug(toolType)}/tttm/check`),
      {
        query: {
          fab_name: fabName,
          ...(recipeId ? { recipe_id: recipeId } : {}),
          ...(recipeId && parameter ? { parameter } : {})
        }
      }
    )

  // `recipeId`/`parameter` are getters, not plain strings, because the user
  // picks them in the page: a value baked into the key at call time would never
  // refetch. The key deliberately omits both so one cache entry per (tool, fab)
  // is reused and re-fetched, rather than accumulating one entry per scope ever
  // viewed.
  const useTttmCheck = (
    toolType: string,
    fabName: string,
    recipeId?: () => string | null | undefined,
    parameter?: () => string | null | undefined
  ) => {
    const sources = [recipeId, parameter].filter(Boolean) as (() => unknown)[]
    return useAsyncData(
      `tttm-check:${toolType}:${fabName}`,
      () => fetchTttmCheck(
        toolType,
        fabName,
        recipeId?.() ?? undefined,
        parameter?.() ?? undefined
      ),
      sources.length ? { watch: sources } : {}
    )
  }

  return { fetchTttmCheck, useTttmCheck }
}
