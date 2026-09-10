import { joinApiPath } from '~/utils/apiPath'
import { recipePairSetKey } from '~/utils/recipePair'
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

/**
 * A recipe as the compare REQUEST body spells it.
 *
 * `recipe_name` here and `recipe_id` in the response are THE SAME STRING —
 * the catalog's `"class/recipe"` value (recipe_search/MIGRATION.md). The two
 * spellings are a wire-contract fact, not two concepts, and renaming the
 * request field would be a backend contract change for cosmetics.
 *
 * So this is the only place the frontend says `recipe_name`:
 * `recipesForCompare` produces these refs, `fetchCompare` posts them, and
 * everything downstream speaks `recipe_id` through `CompareColumn`.
 */
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

// toolSlug now comes from ~/utils/toolType via Nuxt auto-import.

const inFlightCompares = new Map<string, Promise<RecipeCompareResponse>>()

export const useRecipeCompareApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchCompare = async (params: RecipeCompareParams): Promise<RecipeCompareResponse> => {
    const slug = toolSlug(params.toolType)
    // Trim before the filter AND before the wire: filtering on `.trim()` while
    // sending the raw name lets a padded name reach the backend, where it fails
    // to match a registry key that the untrimmed name never had. It also splits
    // the in-flight cache, so ' A ' and 'A' each open their own request.
    const refs = params.recipes
      .map(r => ({ ...r, recipe_name: r.recipe_name.trim() }))
      .filter(r => r.recipe_name)
    const cacheKey = `${params.toolType}:${recipePairSetKey(refs)}`
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
