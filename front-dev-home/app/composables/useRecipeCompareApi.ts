import { joinApiPath } from '~/utils/apiPath'
import type { IdpLocator, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { ImageSlotKey } from '~/utils/recipeView'

export interface CompareIdpFields {
  Addressing: boolean
  Double_Addressing: boolean
  Mother_Para: boolean
  Region: number
  Meas_Counting: number
  dnumber_removed: boolean
}

export interface CompareParameter {
  Parameter: string
  idp: CompareIdpFields
  /** The five img_* values verbatim — posted straight back as param-detail's `slots`. */
  images: Record<ImageSlotKey, string>
}

export interface CompareRecipe {
  recipe_id: string
  fab_name: string
  /** Per recipe, because each one's raw folder lives on its own tool. */
  locator: IdpLocator
  parameters: CompareParameter[]
}

export interface CompareRecipeRef {
  recipe_name: string
  fab_name: string
}

export interface RecipeCompareResponse {
  tool_type: RecipeSearchToolType
  fab_names: string[]
  recipes: CompareRecipe[]
}

export interface RecipeCompareParams {
  toolType: RecipeSearchToolType
  recipes: CompareRecipeRef[]
}

const TOOL_TO_BACKEND_SLUG: Record<RecipeSearchToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

const inFlightCompares = new Map<string, Promise<RecipeCompareResponse>>()

export const useRecipeCompareApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchCompare = async (params: RecipeCompareParams): Promise<RecipeCompareResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const refs = params.recipes.filter(r => r.recipe_name.trim())
    const cacheKey = `${params.toolType}:${refs.map(r => `${r.fab_name}:${r.recipe_name}`).sort().join('|')}`
    const existing = inFlightCompares.get(cacheKey)

    if (existing) {
      return await existing
    }

    const request = $fetch<RecipeCompareResponse>(
      joinApiPath(base, `/${slug}/recipe-search/compare`),
      {
        method: 'POST',
        body: { recipes: refs }
      }
    ).finally(() => {
      inFlightCompares.delete(cacheKey)
    })

    inFlightCompares.set(cacheKey, request)
    return await request
  }

  return { fetchCompare }
}
