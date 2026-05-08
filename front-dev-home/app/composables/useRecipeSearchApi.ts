import { joinApiPath } from '~/utils/apiPath'

export type RecipeSearchToolType = 'cd-sem' | 'hv-sem'

export interface RecipeSearchRow {
  recipe_id: string
  recipe_name: string
  class_name: string
  fac_id: string
  fab_name: string
  tool_type: RecipeSearchToolType
  eqp_model_cd: string
  updated_at: string
}

export interface RecipeSearchResponse {
  tool_type: RecipeSearchToolType
  fab_name: string | null
  total: number
  rows: RecipeSearchRow[]
}

export interface RecipeSearchParams {
  toolType: RecipeSearchToolType
  fabName?: string
}

const TOOL_TO_BACKEND_SLUG: Record<RecipeSearchToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

const inFlightRecipeLists = new Map<string, Promise<RecipeSearchResponse>>()

export const useRecipeSearchApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeList = async (params: RecipeSearchParams): Promise<RecipeSearchResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const fabName = params.fabName?.trim().toUpperCase()
    const cacheKey = `${params.toolType}:${fabName || 'ALL'}`
    const existing = inFlightRecipeLists.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query = fabName ? { fab_name: fabName } : undefined
    const request = $fetch<RecipeSearchResponse>(
      joinApiPath(base, `/${slug}/recipe-search/recipes`),
      { query }
    ).finally(() => {
      inFlightRecipeLists.delete(cacheKey)
    })

    inFlightRecipeLists.set(cacheKey, request)
    return await request
  }

  return {
    fetchRecipeList
  }
}
