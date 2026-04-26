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

const joinStorageApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const useStorageApi = () => {
  const config = useRuntimeConfig()
  const storageUrl = joinStorageApiPath(config.public.apiBase, '/storage')

  const fetchStorageRows = async (facIds: string[] = []): Promise<StorageRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<StorageRow[]>(storageUrl, { query })
  }

  // Storage rows are aggregated at the fac level. The URL's fab segment may be a fab_name
  // (e.g. "M16A", "R3", "R4"), but storage shows everything under its parent fac — same approach
  // as device-statistics.vue. Pure fab_name filtering is left to the page if it ever needs it.
  const fetchByUrlFab = async (urlFab: string): Promise<StorageRow[]> => {
    const facId = fabNameToFacId(urlFab)
    return await fetchStorageRows([facId])
  }

  return {
    fetchStorageRows,
    fetchByUrlFab
  }
}
