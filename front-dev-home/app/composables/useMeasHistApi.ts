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

  return { fetchMeasHist }
}
