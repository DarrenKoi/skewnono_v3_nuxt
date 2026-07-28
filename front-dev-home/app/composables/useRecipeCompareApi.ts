import { joinApiPath } from '~/utils/apiPath'
import type { AmpRow, RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { ImageSlotKey } from '~/utils/recipeView'
import { normalizeFab } from '~/utils/fab'

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
  images: Record<ImageSlotKey, string>
  amp: AmpRow[]
}

export interface CompareRecipe {
  recipe_id: string
  fac_id: string
  parameters: CompareParameter[]
}

export interface RecipeCompareResponse {
  tool_type: RecipeSearchToolType
  fab_name: string | null
  recipes: CompareRecipe[]
}

export interface RecipeCompareParams {
  toolType: RecipeSearchToolType
  fabName?: string
  recipeNames: string[]
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
    const fabName = normalizeFab(params.fabName)
    const names = params.recipeNames.map(name => name.trim()).filter(Boolean)
    const cacheKey = `${params.toolType}:${fabName || 'ALL'}:${[...names].sort().join('|')}`
    const existing = inFlightCompares.get(cacheKey)

    if (existing) {
      return await existing
    }

    const request = $fetch<RecipeCompareResponse>(
      joinApiPath(base, `/${slug}/recipe-search/compare`),
      {
        method: 'POST',
        body: { recipe_names: names, ...(fabName ? { fab_name: fabName } : {}) }
      }
    ).finally(() => {
      inFlightCompares.delete(cacheKey)
    })

    inFlightCompares.set(cacheKey, request)
    return await request
  }

  return { fetchCompare }
}
