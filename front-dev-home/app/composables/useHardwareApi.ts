import { joinApiPath } from '~/utils/apiPath'

export type HardwareToolType = 'cd-sem' | 'hv-sem'
export type HardwareServiceKey = 'bsm' | 'fdc' | 'bm-pm'

export interface HardwarePayload {
  tool_slug: 'cdsem' | 'hvsem'
  service: HardwareServiceKey
  eqp_id: string | null
  fab_id: string | null
  available: boolean
  fetched_at: string
  summary: string
  details: Record<string, unknown>
}

export interface HardwareQuery {
  toolType: HardwareToolType
  service: HardwareServiceKey
  eqpId?: string
  fabId?: string
}

const toolSlug = (toolType: HardwareToolType): 'cdsem' | 'hvsem' =>
  toolType === 'hv-sem' ? 'hvsem' : 'cdsem'

export const useHardwareApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchService = async (params: HardwareQuery): Promise<HardwarePayload> => {
    const query: Record<string, string> = {}
    if (params.eqpId) query.eqp_id = params.eqpId
    if (params.fabId) query.fab_id = params.fabId

    return await $fetch<HardwarePayload>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/hardware/${params.service}`),
      { query }
    )
  }

  return { fetchService }
}
