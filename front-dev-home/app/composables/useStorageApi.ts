import { fabNameToFacId } from '~/composables/useSemListApi'

export interface StorageRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  total: string
  used: string
  avail: string
  percent: string
  storage_mt: string
  rcp_counts: number
  rcp_counts_mt: string
  storage_mt_date: string
  fab_name: string
  eqp_model_cd: string
}

export type UnavailableReason = 'unreachable' | 'stale' | 'never_reported' | 'auth_failed'

export interface UnavailableRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  fab_name: string
  eqp_model_cd: string
  reason: UnavailableReason
  error_code: string
  last_attempt: string
  last_success: string
}

// Storage is now namespaced per ebeam tool (matches back_dev_home/ebeam/<tool>/storage/).
// Frontend ToolType uses kebab-case ('cd-sem'); backend folders use no-hyphen ('cdsem').
export type StorageTool = 'cd-sem' | 'hv-sem'

const TOOL_TO_BACKEND_SLUG: Record<StorageTool, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

const joinStorageApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const useStorageApi = (tool: StorageTool = 'cd-sem') => {
  const config = useRuntimeConfig()
  const slug = TOOL_TO_BACKEND_SLUG[tool]
  const storageUrl = joinStorageApiPath(config.public.apiBase, `/${slug}/storage`)
  const unavailableUrl = joinStorageApiPath(config.public.apiBase, `/${slug}/storage-unavailable`)

  const fetchStorageRows = async (facIds: string[] = []): Promise<StorageRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<StorageRow[]>(storageUrl, { query })
  }

  const fetchUnavailableRows = async (facIds: string[] = []): Promise<UnavailableRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<UnavailableRow[]>(unavailableUrl, { query })
  }

  // Storage rows are aggregated at the fac level. The URL's fab segment may be a fab_name
  // (e.g. "M16A", "R3", "R4"), but storage shows everything under its parent fac — same approach
  // as device-statistics.vue. Pure fab_name filtering is left to the page if it ever needs it.
  const fetchByUrlFab = async (urlFab: string): Promise<StorageRow[]> => {
    const facId = fabNameToFacId(urlFab)
    return await fetchStorageRows([facId])
  }

  const fetchUnavailableByUrlFab = async (urlFab: string): Promise<UnavailableRow[]> => {
    const facId = fabNameToFacId(urlFab)
    return await fetchUnavailableRows([facId])
  }

  return {
    fetchStorageRows,
    fetchByUrlFab,
    fetchUnavailableRows,
    fetchUnavailableByUrlFab
  }
}
