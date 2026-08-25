import { joinApiPath } from '~/utils/apiPath'
import type { WindowWeeks } from '~/utils/analysisWindow'
import type { SkewMatrix, Confidence, Tier } from '~/utils/tttmGrouping'

// `eqp_model_cd` is the raw sem_list model code (CG6300, TP4500, …). The fleet
// picker groups its chips by it — see utils/tttmToolGroups.
export interface ToolRef { eqp_id: string, label: string, eqp_model_cd: string }

/** One recipe this fab has actually measured, with the evidence behind it. */
export interface TttmRecipeRow {
  /** Pass back as `recipe_id`; the `class/recipe` full name where there is one. */
  recipe_id: string
  fab_name: string
  runs: number
  /** Distinct tools that ran it. 1 means no pair exists, so no direct skew. */
  tools: number
}

export interface TttmRecipeList {
  tool_slug: string
  fab_name: string
  /** The window the rows were counted over — the check's window, echoed. */
  window_weeks: number
  fetched_at: string
  rows: TttmRecipeRow[]
}

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
  /**
   * Every parameter name measured under `recipe_id` — the picker's catalogue,
   * read off the same rows the skew is computed from. Always the UNFILTERED
   * set; `[]` without a recipe and on every unavailable branch.
   */
  parameters: string[]
  /**
   * How far back the runs were gathered, in weeks — echoed from the request,
   * including on unavailable answers. Bounds the per-tool run cap at the
   * office as well as the lookback, so a wider window is more evidence.
   */
  window_weeks: number
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
  //
  // `windowWeeks` is always sent (the store normalises it to a choice the
  // server accepts), so the label the page shows and the span the server
  // gathered cannot come apart on a default that differs between the two.
  const fetchTttmCheck = (
    toolType: string,
    fabName: string,
    recipeId: string | undefined,
    parameter: string | undefined,
    windowWeeks: WindowWeeks
  ) =>
    $fetch<TttmCheckPayload>(
      joinApiPath(base, `/${toSlug(toolType)}/tttm/check`),
      {
        query: {
          fab_name: fabName,
          window_weeks: windowWeeks,
          ...(recipeId ? { recipe_id: recipeId } : {}),
          ...(recipeId && parameter ? { parameter } : {})
        }
      }
    )

  // `recipeId`/`parameter`/`windowWeeks` are getters, not plain values,
  // because the user picks them in the page: a value baked into the key at
  // call time would never refetch. The key deliberately omits all three so one
  // cache entry per (tool, fab) is reused and re-fetched, rather than
  // accumulating one entry per scope ever viewed.
  const useTttmCheck = (
    toolType: string,
    fabName: string,
    recipeId: () => string | null | undefined,
    parameter: () => string | null | undefined,
    windowWeeks: () => WindowWeeks
  ) =>
    useAsyncData(
      `tttm-check:${toolType}:${fabName}`,
      () => fetchTttmCheck(
        toolType,
        fabName,
        recipeId() ?? undefined,
        parameter() ?? undefined,
        windowWeeks()
      ),
      { watch: [recipeId, parameter, windowWeeks] }
    )

  // The picker's source. Deliberately NOT recipe-search's catalogue: that
  // lists every recipe that EXISTS, and on these screens a recipe nobody ran
  // can only ever answer "no data". `runs`/`tools` come back so the picker can
  // rank by evidence and mark the recipes only one tool measured — those can
  // never produce a pair, however many runs they have.
  //
  // Windowed like the check, because it lists what the check will find: a
  // recipe measured four weeks ago is on a 3-week list only if it ran again.
  const fetchTttmRecipes = (toolType: string, fabName: string, windowWeeks: WindowWeeks) =>
    $fetch<TttmRecipeList>(
      joinApiPath(base, `/${toSlug(toolType)}/tttm/recipes`),
      { query: { fab_name: fabName, window_weeks: windowWeeks } }
    )

  return { fetchTttmCheck, useTttmCheck, fetchTttmRecipes }
}
