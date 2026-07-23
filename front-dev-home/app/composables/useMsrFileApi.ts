import { joinApiPath } from '~/utils/apiPath'

// The cross-MSR compatibility signature is extracted STRUCTURALLY from
// MsrFileResponse — every field the signature reads (recipe identity, per-param
// unit, coordinate metadata, per-row acquisition fields) already lives on this
// response. All manifest/compatibility logic is framework-free and stays in
// utils/skewvoirAnalysis; re-exported here so callers have one MSR-file import
// surface. See utils/skewvoirAnalysis/compatibility.ts for the unknown-safe
// contract and the office-gated fields (layout hash, recipe revision, …) this
// response intentionally does NOT carry.
export type {
  AnalysisManifest,
  AnalysisScope,
  CompatibilitySignature,
  ExclusionReason,
  Readiness,
  ReadinessMatrix
} from '~/utils/skewvoirAnalysis/types'

export interface MsrFileRow {
  msr: string
  sequence: number
  chip_number: string
  chip_coordinate: string
  stage_coordinate: string
  dnum_group: string
  mp_number: number
  parameter: string
  // NULLABLE: null exactly when mp_number < 0 — a point with metadata but no
  // data has no measurement. Never coerce this to 0; gate it via utils/msrRows.
  cd_value: number | null
  no_of_mp_image: number
  mp_image_name_01: string
  meas_condition_mag: number
  meas_condition_vac: number
  meas_condition_pixel: string
  addressing1_score: number | null
  addressing2_score: number | null
  measurement_score: number | null
  meas_method: string
  object_type: string
  meas_kind: string | null
}

export interface ExeDetailInfo {
  class_name: string
  recipe_name: string
  idp_name: string
  lot_id: string
  process: string
  wafer_id: string
  idw_name: string
  chip_array: string
  chip_pitch: string
  wafer_size: string
  map_offset: string
  map_origin: string
}

export interface AlignmentInfo {
  image_file: Record<string, string>
  // [method, x, y] — e.g. ['OM', '365', '3525']
  offset: Record<string, [string, string, string]>
  score: Record<string, string>
}

// A 32-point profile: Vol (signal) against wf_len (nm). PLACEHOLDER — the mock
// generates a seeded parabola with no signal in it. Nothing consumes this yet;
// do not build analysis on its shape.
export interface SpmDict {
  vave: number[]
  Vol: number[]
  wf_len: number[]
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
  exe_detail_info: ExeDetailInfo
  alignment: AlignmentInfo
  spm_dict: SpmDict
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

// A single request can still 429 if it lands in a window already spent by page
// load, so back off + retry rather than fail the whole panel.
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

  // Fetch a whole selection in ONE request via the batch endpoint. This replaces
  // the old per-MSR fan-out that tripped the 20-req/5s rate limit and left the
  // panel stuck loading; a 200-MSR pick is now a single rate-limit slot.
  // The backend skips not-found MSRs, so we re-key by `msr` and preserve the
  // requested order.
  const fetchMsrFiles = async (list: MsrFileParams[]): Promise<MsrFileResponse[]> => {
    if (list.length === 0) return []

    const body = {
      items: list.map(p => ({
        msr: p.msr.trim(),
        class_name: p.className ?? null,
        total_images: p.totalImages ?? null
      }))
    }

    let responses: MsrFileResponse[] = []
    for (let i = 0; ; i++) {
      try {
        const res = await $fetch<{ results: MsrFileResponse[] }>(
          joinApiPath(base, '/msr-files'),
          { method: 'POST', body }
        )
        responses = res.results
        break
      } catch (err) {
        if (statusOf(err) === 429 && i < MAX_RETRIES) {
          await sleep(700 * 2 ** i)
          continue
        }
        throw err
      }
    }

    const byMsr = new Map(responses.map(res => [res.msr, res]))
    return list
      .map(p => byMsr.get(p.msr.trim()))
      .filter((res): res is MsrFileResponse => res != null)
  }

  return { fetchMsrFile, fetchMsrFiles }
}
