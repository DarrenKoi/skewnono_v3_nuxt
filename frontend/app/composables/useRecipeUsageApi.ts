import { joinApiPath } from '~/utils/apiPath'

// Mirrors backend/ebeam/recipe_usage/contracts.py. AMAT families only: the
// Hitachi recipe pages read a different model (IDP files, lot_cd, align/meas
// fail split) through useRecipeSearchApi / useRecipeTatApi / useFailIssueApi.
export type RecipeUsageToolType = 'veritysem' | 'provision'

// mes = a job started through MES, file not on a tool now.
// tool = resident on a tool, never started through MES.
export type RecipeUsageSource = 'mes' | 'tool' | 'both'

export interface RecipeUsageCatalogRow {
  recipe_id: string
  fab_name: string
  // Provision only; '' for VeritySEM.
  product_id: string
  layer_id: string
  recipe_name: string
  eqp_ids: string[]
  // All-time JobStart count.
  n_uses: number
  // KST strings as stored. null when source === 'tool'.
  first_used: string | null
  last_used: string | null
  source: RecipeUsageSource
}

export interface RecipeUsageCatalogResponse {
  tool_type: RecipeUsageToolType
  fab_names: string[]
  total: number
  rows: RecipeUsageCatalogRow[]
}

export interface RecipeUsageToolRow {
  eqp_id: string
  fab_name: string
  n_uses: number
  first_used: string | null
  last_used: string | null
  on_tool: boolean
}

export interface RecipeUsageDailyPoint {
  date: string
  runs: number
  wafers: number
  meas_min: number
  fail_runs: number
}

export interface RecipeUsageDetailResponse {
  tool_type: RecipeUsageToolType
  recipe_id: string
  fab_names: string[]
  // [] for an unknown recipe; the endpoint never 404s.
  tools: RecipeUsageToolRow[]
  // Loaded partitions only, ascending, days without a run omitted.
  daily: RecipeUsageDailyPoint[]
}

export interface RecipeUsageStatusSummary {
  runs: number
  wafers: number
  meas_min: number
  fail_runs: number
  fail_rate: number
  // meas_min / runs. A run that never ended counts 0 minutes, so this reads
  // low when fail_runs is high.
  avg_meas_min: number
  recipe_count: number
  active_tool_count: number
  tool_count: number
}

export interface RecipeUsageRankingRow {
  recipe_id: string
  runs: number
  wafers: number
  meas_min: number
  avg_meas_min: number
  fail_runs: number
  fail_rate: number
  eqp_ids: string[]
  fab_names: string[]
  last_start: string
}

// One per roster tool; a tool with no run in the window is present with zeros.
export interface RecipeUsageEquipmentRow {
  eqp_id: string
  fab_name: string
  eqp_model_cd: string
  runs: number
  wafers: number
  meas_min: number
  avg_meas_min: number
  fail_runs: number
  fail_rate: number
  recipe_count: number
  top_recipe: string | null
  last_start: string | null
}

export interface RecipeUsageStatusResponse {
  tool_type: RecipeUsageToolType
  fab_names: string[]
  start_date: string
  end_date: string
  // Latest date with rows: yesterday at best.
  anchor_date: string | null
  // Earliest date with rows.
  data_start: string | null
  summary: RecipeUsageStatusSummary
  // Every calendar day in the window, zero-filled.
  daily: RecipeUsageDailyPoint[]
  recipes: RecipeUsageRankingRow[]
  equipments: RecipeUsageEquipmentRow[]
}

export const useRecipeUsageApi = () => {
  const base = useRuntimeConfig().public.apiBase

  const get = <T>(
    toolType: RecipeUsageToolType,
    leaf: string,
    fabNames: readonly string[],
    extra: Record<string, string | undefined> = {}
  ) => {
    const query: Record<string, string> = {}
    if (fabNames.length) query.fab_name = fabNames.join(',').toUpperCase()
    for (const [key, value] of Object.entries(extra)) {
      if (value) query[key] = value
    }
    return $fetch<T>(joinApiPath(base, `/${toolSlug(toolType)}/recipe-usage/${leaf}`), { query })
  }

  return {
    fetchRecipeUsageCatalog: (toolType: RecipeUsageToolType, fabNames: readonly string[]) =>
      get<RecipeUsageCatalogResponse>(toolType, 'recipes', fabNames),

    fetchRecipeUsageDetail: (toolType: RecipeUsageToolType, fabNames: readonly string[], recipeId: string) =>
      get<RecipeUsageDetailResponse>(toolType, 'recipe', fabNames, { recipe_id: recipeId }),

    // Omitted dates let the backend resolve its default window (14 days ending
    // at anchor_date); guessing wall-clock today would overshoot the data.
    fetchRecipeUsageStatus: (
      toolType: RecipeUsageToolType,
      fabNames: readonly string[],
      range: { start?: string, end?: string } = {}
    ) => get<RecipeUsageStatusResponse>(toolType, 'status', fabNames, {
      start_date: range.start,
      end_date: range.end
    })
  }
}

/** The recipe whose detail drawer is open, kept in `?recipe=` so a link to it
 *  survives a reload. Shared by Recipe 검색 and Recipe 현황. */
export const useRecipeUsageSelection = () => {
  const route = useRoute()
  const router = useRouter()

  const selectedRecipe = computed(() => {
    const raw = Array.isArray(route.query.recipe) ? route.query.recipe[0] : route.query.recipe
    return typeof raw === 'string' && raw ? raw : null
  })

  const selectRecipe = (recipeId: string | null) => {
    const { recipe: _dropped, ...rest } = route.query
    router.replace({ query: recipeId ? { ...rest, recipe: recipeId } : rest })
  }

  return { selectedRecipe, selectRecipe }
}
