import { joinApiPath } from '~/utils/apiPath'
import { canonicalFabList } from '~/utils/fab'
import { recipePairSetKey } from '~/utils/recipePair'
import type { RegistryCheckResult } from '~/utils/recipeSearchMatch'
import type { ToolType } from '~/utils/toolType'

/** @deprecated 이름만 유지. 새 코드는 ToolType 을 직접 씁니다. */
export type RecipeSearchToolType = ToolType

export interface RecipeSearchRow {
  recipe_name: string
  fab_name: string
}

export interface RecipeSearchResponse {
  tool_type: RecipeSearchToolType
  fab_names: string[]
  total: number
  rows: RecipeSearchRow[]
}

export interface RecipeSearchParams {
  toolType: RecipeSearchToolType
  fabNames?: string[]
}

export interface RecipeDetailParams {
  toolType: RecipeSearchToolType
  // A detail lookup is owned by exactly one fab (the recipe's home fab), so
  // this stays singular even though the list endpoint takes fabNames.
  fabName?: string
  recipeName: string
}

export interface WaferMpInfoRow {
  ChipNo_X: number
  ChipNo_Y: number
  Coordinate_X: number
  Coordinate_Y: number
  P_No: number
  D_No: number
  Diff: boolean | null
  Rel: boolean | null
  Rel_MoveX: number
  Rel_MoveY: number
  Coordinate_X_r: number
  Coordinate_Y_r: number
  Parameter: string
  /** Not a filename despite the name — carries the same value as P_No. The
   *  identically-named field on IdpImageInfoRow IS an image slot. */
  img_meas2: number
}

export interface WaferAlignInfoRow {
  'Align_No': number
  'Chip.X': number
  'Chip.Y': number
  'Coordinate.X': number
  'Coordinate.Y': number
  'P.No': number
}

export interface IdpImageInfoRow {
  Parameter: string
  img_add1: string
  img_add2: string
  img_meas1: string
  img_meas2: string
  SEQ: number
  Last_SEQ: number
  Region: number
  image_add3: string
  Addressing: boolean | null
  /** True when this row's own parameter is a mother — sons measure from its image. */
  Mother_Para: boolean | null
  Double_Addressing: boolean | null
  Meas_Counting: number
  /** True when the parameter's data is suppressed and never reaches the legacy system. */
  dnumber_removed: boolean | null
}

/**
 * Where this recipe's raw folder lives on the measuring tool's FTP server.
 * Carried so param-detail, align-detail and recipe-image reach it without
 * re-downloading or re-parsing the .idp.
 */
export interface IdpLocator {
  eqp_ip: string
  class_name: string
  idw: string
  idp: string
}

export interface RecipeDetailResponse {
  wafer_mp_info: WaferMpInfoRow[]
  wafer_align_info: WaferAlignInfoRow[]
  idp_image_info: IdpImageInfoRow[]
  locator: IdpLocator
  recipe_id: string
  fab_name: string
  tool_category: RecipeSearchToolType
  timestamp: string
}

/**
 * Tier 0 of the recipe read endpoints — every idp_image_info row of one recipe,
 * no tool I/O. The cheap tier on purpose: `amp`/`af_pr` cost up to five FTP
 * reads per occurrence off the measuring tool itself, and listing parameters
 * must not pay that.
 *
 * `rows` is one image DEFINITION each, so a parameter can occupy several rows —
 * `distinct_parameters` is the count a user actually means, carried so callers
 * do not have to dedupe to get it right.
 */
export interface ParameterListResponse {
  recipe_id: string
  fab_name: string | null
  tool_type: RecipeSearchToolType
  locator: IdpLocator
  total_rows: number
  distinct_parameters: number
  mother_rows: number
  addressing_rows: number
  rows: IdpImageInfoRow[]
}

export interface RegistryCheckParams {
  toolType: RecipeSearchToolType
  recipes: Array<{ recipe_name: string, fab_name: string }>
}

export interface RegistryCheckResponse {
  tool_type: RecipeSearchToolType
  results: RegistryCheckResult[]
}

// toolSlug now comes from ~/utils/toolType via Nuxt auto-import (registry's
// version); this file no longer declares its own.

const inFlightRecipeLists = new Map<string, Promise<RecipeSearchResponse>>()
const inFlightRecipeDetails = new Map<string, Promise<RecipeDetailResponse>>()
const inFlightRegistryChecks = new Map<string, Promise<RegistryCheckResponse>>()

export const useRecipeSearchApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeList = async (params: RecipeSearchParams): Promise<RecipeSearchResponse> => {
    const slug = toolSlug(params.toolType)
    const fabKey = canonicalFabList(params.fabNames ?? []).join(',')
    const cacheKey = `${params.toolType}:${fabKey || 'ALL'}`
    const existing = inFlightRecipeLists.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query = fabKey ? { fab_name: fabKey } : undefined
    const request = $fetch<RecipeSearchResponse>(
      joinApiPath(base, `/${slug}/recipe-search/recipes`),
      { query }
    ).finally(() => {
      inFlightRecipeLists.delete(cacheKey)
    })

    inFlightRecipeLists.set(cacheKey, request)
    return await request
  }

  const fetchRecipeDetail = async (params: RecipeDetailParams): Promise<RecipeDetailResponse> => {
    const slug = toolSlug(params.toolType)
    const fabName = normalizeFab(params.fabName)
    const recipeName = params.recipeName.trim()
    const cacheKey = `${params.toolType}:${fabName || 'ALL'}:${recipeName}`
    const existing = inFlightRecipeDetails.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query = {
      recipe_name: recipeName,
      ...(fabName ? { fab_name: fabName } : {})
    }
    const request = $fetch<RecipeDetailResponse>(
      joinApiPath(base, `/${slug}/recipe-search/recipe-detail`),
      { query }
    ).finally(() => {
      inFlightRecipeDetails.delete(cacheKey)
    })

    inFlightRecipeDetails.set(cacheKey, request)
    return await request
  }

  /**
   * Which of these recipes the Redis recipe registry can place, one request
   * for the batch.
   *
   * POST because the batch is a body, and because 50 GETs would spend the
   * whole 50 req / 5 s budget on one question. Same in-flight dedup as the
   * three fetchers above and as `useRecipeCompareApi`, keyed by the same
   * `recipePairSetKey` — the caller marks a pair answered only when the
   * RESPONSE lands, so paging away and back mid-flight otherwise re-asks the
   * identical batch. Normalized before the key as well as before the wire, or
   * ' A ' and 'A' would open two requests for one question.
   */
  const checkRecipeRegistry = async (
    params: RegistryCheckParams
  ): Promise<RegistryCheckResponse> => {
    const slug = toolSlug(params.toolType)
    const refs = params.recipes
      .map(recipe => ({
        recipe_name: recipe.recipe_name.trim(),
        fab_name: normalizeFab(recipe.fab_name)
      }))
      .filter(recipe => recipe.recipe_name)
    const cacheKey = `${params.toolType}:${recipePairSetKey(refs)}`
    const existing = inFlightRegistryChecks.get(cacheKey)

    if (existing) {
      return await existing
    }

    const request = $fetch<RegistryCheckResponse>(
      joinApiPath(base, `/${slug}/recipe-search/registry-check`),
      {
        method: 'POST',
        body: { recipes: refs }
      }
    ).finally(() => {
      inFlightRegistryChecks.delete(cacheKey)
    })

    inFlightRegistryChecks.set(cacheKey, request)
    return await request
  }

  return {
    checkRecipeRegistry,
    fetchRecipeDetail,
    fetchRecipeList
  }
}
