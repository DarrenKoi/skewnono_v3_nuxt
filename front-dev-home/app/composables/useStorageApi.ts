import { joinApiPath } from '~/utils/apiPath'
import type { SEM_TOOL_TYPES } from '~/utils/toolType'

export interface StorageRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  total: string
  used: string
  avail: string
  percent: string
  storage_mt: string | null
  rcp_counts: number
  rcp_counts_mt: string
  storage_mt_date: string
  fab_name: string
  eqp_model_cd: string
}

// A tool whose storage collection failed: no sample timestamp or no avail value.
// Mirrors back_dev_home storage data.py (storage_mt is None / avail is "").
export const isStorageUnavailable = (row: StorageRow): boolean =>
  !row.storage_mt || !row.avail

export interface PpidUnavailableRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  fab_name: string
  eqp_model_cd: string
  missing_days_streak: number
}

export interface PpidUnavailableSnapshot {
  latest_date: string
  rows: PpidUnavailableRow[]
}

// Storage is now namespaced per ebeam tool (matches back_dev_home/ebeam/<tool>/storage/).
// Frontend ToolType uses kebab-case ('cd-sem'); backend folders use no-hyphen ('cdsem').
// Hitachi-only feature, narrower than the full ToolType registry on purpose.
export type StorageTool = (typeof SEM_TOOL_TYPES)[number]

const TOOL_TO_BACKEND_SLUG: Record<StorageTool, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem'
}

export const useStorageApi = (tool: StorageTool = 'cd-sem') => {
  const config = useRuntimeConfig()
  const slug = TOOL_TO_BACKEND_SLUG[tool]
  const storageUrl = joinApiPath(config.public.apiBase, `/${slug}/storage`)
  const ppidUnavailableUrl = joinApiPath(config.public.apiBase, `/${slug}/ppid-unavailable`)

  const fetchStorageRows = async (fabNames: string[] = [], signal?: AbortSignal): Promise<StorageRow[]> => {
    const query = fabNames.length > 0 ? { fab_name: fabNames.join(',') } : undefined

    return await $fetch<StorageRow[]>(storageUrl, { query, signal })
  }

  const fetchPpidUnavailableRows = async (fabNames: string[] = [], signal?: AbortSignal): Promise<PpidUnavailableSnapshot> => {
    const query = fabNames.length > 0 ? { fab_name: fabNames.join(',') } : undefined

    return await $fetch<PpidUnavailableSnapshot>(ppidUnavailableUrl, { query, signal })
  }

  return {
    fetchStorageRows,
    fetchPpidUnavailableRows
  }
}
