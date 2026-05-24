import { joinApiPath } from '~/utils/apiPath'

export type HardwareToolType = 'cd-sem' | 'hv-sem'
export type HardwareServiceKey = 'bsm' | 'fdc' | 'bm-pm'
export type HardwareMetricTone = 'neutral' | 'ok' | 'warning' | 'bad'
export type HardwareMetricValue = string | number | boolean | null

export interface HardwareMetricCard {
  key: string
  label: string
  value: HardwareMetricValue
  unit?: string
  tone?: HardwareMetricTone
}

export interface HardwareTableColumn {
  key: string
  label: string
  // Long free-text columns (e.g. engr_note) render truncated with a
  // click-to-expand toggle instead of a wide nowrap cell.
  expandable?: boolean
}

export interface HardwareTableSection {
  key: string
  title: string
  columns: HardwareTableColumn[]
  rows: Record<string, HardwareMetricValue>[]
}

export interface BsmSummaryRow {
  timestamp: string
  eqp_id: string
  sharpness_avg: number
  sharpness_3std: number
  noise_avg: number
  noise_3std: number
}

export interface BsmProfile {
  // Parallel to BsmBlock.angles: one value per 22.5° step.
  sharpness: number[]
  noise: number[]
}

export interface BsmCategory {
  key: string
  label: string
  summary: BsmSummaryRow[]
  // Raw 360° profiles keyed by the summary row's timestamp (the join key the
  // radar uses on row/point click).
  profiles: Record<string, BsmProfile>
}

export interface BsmBlock {
  angles: string[]
  categories: BsmCategory[]
}

export type BsmMetric = 'sharpness' | 'noise'

export interface HardwarePayload {
  tool_slug: 'cdsem' | 'hvsem'
  service: HardwareServiceKey
  eqp_id: string | null
  fab_id: string | null
  available: boolean
  fetched_at: string
  summary: string
  cards: HardwareMetricCard[]
  tables: HardwareTableSection[]
  // Present only for the BSM service.
  bsm?: BsmBlock
  raw?: Record<string, HardwareMetricValue>
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
