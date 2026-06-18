import { joinApiPath } from '~/utils/apiPath'

export type HardwareToolType = 'cd-sem' | 'hv-sem'
export type HardwareServiceKey = 'bsm' | 'reso-center' | 'fdc' | 'mdc' | 'sce' | 'bm-pm'
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

export interface HardwarePayload {
  tool_slug: 'cdsem' | 'hvsem'
  service: HardwareServiceKey
  eqp_id: string | null
  fab_name: string | null
  available: boolean
  fetched_at: string
  summary: string
  cards: HardwareMetricCard[]
  tables: HardwareTableSection[]
  // bsm / reso-center / fdc → faithful raw docs (ascending time).
  docs?: Record<string, unknown>[]
  // mdc / sce → dict-of-dict keyed by eqp_id (selected eqp + in-fab siblings).
  settings?: Record<string, Record<string, unknown>>
  raw?: Record<string, HardwareMetricValue>
}

export interface HardwareQuery {
  toolType: HardwareToolType
  service: HardwareServiceKey
  eqpId?: string
  fabName?: string
  start?: string
  end?: string
}

const toolSlug = (toolType: HardwareToolType): 'cdsem' | 'hvsem' =>
  toolType === 'hv-sem' ? 'hvsem' : 'cdsem'

export const useHardwareApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchService = async (params: HardwareQuery): Promise<HardwarePayload> => {
    const query: Record<string, string> = {}
    if (params.fabName) query.fab_name = params.fabName
    if (params.start) query.start = params.start
    if (params.end) query.end = params.end

    const eqpSegment = params.eqpId ?? '_'
    return await $fetch<HardwarePayload>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/hardware/${eqpSegment}/${params.service}`),
      { query }
    )
  }

  return { fetchService }
}
