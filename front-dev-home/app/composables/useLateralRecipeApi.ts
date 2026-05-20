import { joinApiPath } from '~/utils/apiPath'

export type LateralRecipeToolType = 'cd-sem' | 'hv-sem'

export interface LateralRecipeRow {
  eqp_id: string
  eqp_model_cd: string
  vendor_nm: 'HITACHI' | 'AMAT'
  available: 'On' | 'Off'
  recipe_ready: boolean
  recipe_version: number | null
  recipe_generated_at: string | null
}

export interface LateralRecipeVersion {
  recipe_version: number
  generated_at: string
  ready_count: number
}

export interface LateralRecipeResponse {
  tool_type: LateralRecipeToolType
  fab_name: string | null
  recipe_name: string
  total_tools_in_fab: number
  ready_count: number
  not_ready_count: number
  latest_recipe_version: number | null
  latest_generated_at: string | null
  versions: LateralRecipeVersion[]
  rows: LateralRecipeRow[]
}

export interface LateralRecipeParams {
  toolType: LateralRecipeToolType
  fabName?: string
  recipeName: string
}

const TOOL_TO_BACKEND_SLUG: Record<LateralRecipeToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

const inFlight = new Map<string, Promise<LateralRecipeResponse>>()

export const useLateralRecipeApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchLateralRecipe = async (params: LateralRecipeParams): Promise<LateralRecipeResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const fabName = params.fabName?.trim().toUpperCase()
    const recipeName = params.recipeName.trim()
    const cacheKey = `${params.toolType}:${fabName || 'ALL'}:${recipeName}`
    const existing = inFlight.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query = {
      recipe_name: recipeName,
      ...(fabName ? { fab_name: fabName } : {})
    }

    const request = $fetch<LateralRecipeResponse>(
      joinApiPath(base, `/${slug}/recipe-search/lateral`),
      { query }
    ).finally(() => {
      inFlight.delete(cacheKey)
    })

    inFlight.set(cacheKey, request)
    return await request
  }

  return { fetchLateralRecipe }
}
