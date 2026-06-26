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
  measurement_score: number | null
  meas_method: string
  object_type: string
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

export type FdcStatus = 'ok' | 'warning' | 'bad'

// FDC param category (docs/datatables/hardware.txt abnormal-behavior groups).
export type FdcCategory
  = | 'image'
    | 'astigmatism'
    | 'defocus'
    | 'stage_drift'
    | 'source'
    | 'echuck'
    | 'alignment'

export interface FdcParamSummary {
  name: string
  category: FdcCategory
  category_label: string
  unit: string
  nominal: number
  mean: number
  std: number
  min: number
  max: number
  // |mean - nominal| in units of the normal sigma — the abnormality magnitude.
  drift_sigma: number
  status: FdcStatus
}

export interface MsrFileResponse {
  msr: string
  class_name: string
  total_images: number
  sequence_count: number
  // Per-MSR abnormality scalar in [0, 1]; biases both CD drift and FDC drift.
  health: number
  parameters: MsrParamSummary[]
  fdc_params: FdcParamSummary[]
  // Per-MSR scalar FDC (one value per measurement).
  fixed_fdc: Record<string, number>
  // Per-sequence FDC keyed by sequence string → { param: value }.
  dynamic_fdc: Record<string, Record<string, number>>
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

// Bulk selection (e.g. "select all visible") would otherwise fire one request
// per MSR at once and trip the Flask mock's 20-req/5s rate limit. Cap how many
// run concurrently, and back off + retry on 429 so a large pick degrades to
// "slower" instead of "failed".
const MAX_CONCURRENT = 6
const MAX_RETRIES = 4
const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

const statusOf = (err: unknown): number | undefined => {
  const e = err as { response?: { status?: number }, statusCode?: number }
  return e?.response?.status ?? e?.statusCode
}

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

    const attempt = async (): Promise<MsrFileResponse> => {
      for (let i = 0; ; i++) {
        try {
          return await $fetch<MsrFileResponse>(joinApiPath(base, '/msr-file'), { query })
        } catch (err) {
          // Retry only on rate-limit, with exponential backoff inside the 5s window.
          if (statusOf(err) === 429 && i < MAX_RETRIES) {
            await sleep(700 * 2 ** i)
            continue
          }
          throw err
        }
      }
    }

    const request = attempt().finally(() => {
      inFlight.delete(cacheKey)
    })

    inFlight.set(cacheKey, request)
    return await request
  }

  // Run `list` through fetchMsrFile with bounded concurrency, preserving order.
  // Each MSR is deduped independently via fetchMsrFile, so re-selecting is cheap.
  const fetchMsrFiles = async (list: MsrFileParams[]): Promise<MsrFileResponse[]> => {
    const results = new Array<MsrFileResponse>(list.length)
    let next = 0
    const worker = async () => {
      while (next < list.length) {
        const i = next++
        results[i] = await fetchMsrFile(list[i]!)
      }
    }
    const workers = Array.from(
      { length: Math.min(MAX_CONCURRENT, list.length) },
      () => worker()
    )
    await Promise.all(workers)
    return results
  }

  return { fetchMsrFile, fetchMsrFiles }
}
