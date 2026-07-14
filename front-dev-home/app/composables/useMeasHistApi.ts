import { joinApiPath } from '~/utils/apiPath'

export type MeasHistToolType = 'cd-sem' | 'hv-sem'

export interface MeasHistRow {
  id: string
  fac_id: string
  fab_name: string
  vendor_nm: 'HITACHI' | 'AMAT'
  eqp_id: string
  eqp_model_cd: string
  tool_type: MeasHistToolType
  lot_cd: string
  lot_id: string
  class_name: string
  recipe_name: string
  full_name: string
  timestamp: string
  start_time: string
  end_time: string
  meastime: number
  msr: string
  msr_check: 'Yes' | 'No'
  align_fail: 'Pass' | 'Fail' | 'NA'
  total_images: number
  fail_images: number
  fail_ratio: number
  idp_name: string
  idw_name: string
}

export interface MeasHistResponse {
  tool_type: MeasHistToolType | null
  fab_name: string | null
  recipe_name: string | null
  total: number
  rows: MeasHistRow[]
}

export interface MeasHistParams {
  toolType?: MeasHistToolType
  fabName?: string
  recipeName?: string
}

export interface MeasHistFacetValue {
  value: string
  count: number
}

export interface MeasHistFacets {
  tool_type: MeasHistToolType | null
  // The clock the retention window is measured from. Phase 1 pins this to the
  // mock's frozen NOW; never substitute wall-clock today.
  anchor: string
  retention_days: number
  fab: MeasHistFacetValue[]
  model: MeasHistFacetValue[]
  eq: MeasHistFacetValue[]
  recipe: MeasHistFacetValue[]
}

export interface MeasHistSearchParams {
  toolType: MeasHistToolType
  fab?: string[]
  model?: string[]
  eq?: string[]
  recipe?: string[]
  lot?: string[]
  msr?: string[]
  from?: string
  to?: string
  offset?: number
  limit?: number
}

export interface MeasHistSearchResponse {
  total: number
  capped: boolean
  offset: number
  limit: number
  range: { from: string, to: string, anchor: string }
  out_of_retention: boolean
  rows: MeasHistRow[]
}

const inFlight = new Map<string, Promise<MeasHistResponse>>()

export const useMeasHistApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchMeasHist = async (params: MeasHistParams = {}): Promise<MeasHistResponse> => {
    const toolType = params.toolType
    const fabName = params.fabName?.trim().toUpperCase()
    const recipeName = params.recipeName?.trim()
    const cacheKey = `${toolType || 'ALL'}:${fabName || 'ALL'}:${recipeName || 'ALL'}`
    const existing = inFlight.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query: Record<string, string> = {}
    if (toolType) query.tool_type = toolType
    if (fabName) query.fab_name = fabName
    if (recipeName) query.recipe_name = recipeName

    const request = $fetch<MeasHistResponse>(
      joinApiPath(base, '/meas-hist'),
      { query: Object.keys(query).length ? query : undefined }
    ).finally(() => {
      inFlight.delete(cacheKey)
    })

    inFlight.set(cacheKey, request)
    return await request
  }

  const searchMeasHist = async (params: MeasHistSearchParams): Promise<MeasHistSearchResponse> => {
    // Repeated params (?eq=A&eq=B) are how a field ORs its values.
    const query: Record<string, string | string[] | number> = { tool_type: params.toolType }

    for (const key of ['fab', 'model', 'eq', 'recipe', 'lot', 'msr'] as const) {
      const values = params[key]
      if (values?.length) query[key] = values
    }
    if (params.from) query.from = params.from
    if (params.to) query.to = params.to
    if (params.offset) query.offset = params.offset
    if (params.limit) query.limit = params.limit

    return await $fetch<MeasHistSearchResponse>(joinApiPath(base, '/meas-hist/search'), { query })
  }

  const fetchMeasHistFacets = async (toolType: MeasHistToolType): Promise<MeasHistFacets> =>
    await $fetch<MeasHistFacets>(joinApiPath(base, '/meas-hist/facets'), {
      query: { tool_type: toolType }
    })

  return { fetchMeasHist, searchMeasHist, fetchMeasHistFacets }
}
