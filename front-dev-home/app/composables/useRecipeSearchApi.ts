import { joinApiPath } from '~/utils/apiPath'
import { normalizeFab } from '~/utils/fab'

export type RecipeSearchToolType = 'cd-sem' | 'hv-sem'

export interface RecipeSearchRow {
  recipe_name: string
}

export interface RecipeSearchResponse {
  tool_type: RecipeSearchToolType
  fab_name: string | null
  total: number
  rows: string[]
}

export interface RecipeSearchParams {
  toolType: RecipeSearchToolType
  fabName?: string
}

export interface RecipeDetailParams extends RecipeSearchParams {
  recipeName: string
}

export interface WaferMpInfoRow {
  ChipNo_X: number
  ChipNo_Y: number
  Coordinate_X: number
  Coordinate_Y: number
  P_No: number
  D_No: number
  Diff: boolean
  Rel: boolean
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
  Addressing: boolean
  /** True when this row's own parameter is a mother — sons measure from its image. */
  Mother_Para: boolean
  Double_Addressing: boolean
  Meas_Counting: number
  /** True when the parameter's data is suppressed and never reaches the legacy system. */
  dnumber_removed: boolean
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
  fac_id: string
  tool_category: RecipeSearchToolType
  timestamp: string
}

export const TOOL_TO_BACKEND_SLUG: Record<RecipeSearchToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

/** `'hv-sem' -> 'hvsem'`. One table; the raw-folder endpoints need it too. */
export const toolSlug = (toolType: RecipeSearchToolType): string =>
  TOOL_TO_BACKEND_SLUG[toolType]

const inFlightRecipeLists = new Map<string, Promise<RecipeSearchResponse>>()
const inFlightRecipeDetails = new Map<string, Promise<RecipeDetailResponse>>()

export const useRecipeSearchApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeList = async (params: RecipeSearchParams): Promise<RecipeSearchResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const fabName = normalizeFab(params.fabName)
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

  const fetchRecipeDetail = async (params: RecipeDetailParams): Promise<RecipeDetailResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
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

  return {
    fetchRecipeDetail,
    fetchRecipeList
  }
}
