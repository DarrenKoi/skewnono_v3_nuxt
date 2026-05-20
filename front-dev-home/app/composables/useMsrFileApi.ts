import { joinApiPath } from '~/utils/apiPath'

export interface MsrFileRow {
  msr: string
  sequence: number
  chip_number: string
  chip_coordinate: string
  stage_coordinate: string
  dnum_group: string
  mp_number: number
  parameter: string
  cd_value: number
  no_of_mp_image: number
  mp_image_name_01: string
}

export interface MsrParamSummary {
  parameter: string
  count: number
  mean: number
  std: number
  min: number
  max: number
  unit: string
}

export interface MsrFileResponse {
  msr: string
  class_name: string
  total_images: number
  sequence_count: number
  parameters: MsrParamSummary[]
  total: number
  rows: MsrFileRow[]
}

export interface MsrFileParams {
  msr: string
  // Passed from the selected meas_hist row so the backend doesn't have to
  // re-derive them; both optional since the API can fall back to a parent lookup.
  className?: string
  totalImages?: number
}

const inFlight = new Map<string, Promise<MsrFileResponse>>()

export const useMsrFileApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchMsrFile = async (params: MsrFileParams): Promise<MsrFileResponse> => {
    const msr = params.msr.trim()
    const cacheKey = `${msr}:${params.className ?? ''}:${params.totalImages ?? ''}`
    const existing = inFlight.get(cacheKey)
    if (existing) {
      return await existing
    }

    const query: Record<string, string> = { msr }
    if (params.className) query.class_name = params.className
    if (params.totalImages != null) query.total_images = String(params.totalImages)

    const request = $fetch<MsrFileResponse>(
      joinApiPath(base, '/msr-file'),
      { query }
    ).finally(() => {
      inFlight.delete(cacheKey)
    })

    inFlight.set(cacheKey, request)
    return await request
  }

  // Each MSR is deduped independently via fetchMsrFile, so re-selecting is cheap.
  const fetchMsrFiles = async (list: MsrFileParams[]): Promise<MsrFileResponse[]> => {
    return await Promise.all(list.map(params => fetchMsrFile(params)))
  }

  return { fetchMsrFile, fetchMsrFiles }
}
