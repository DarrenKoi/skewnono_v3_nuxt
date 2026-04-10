import type { Fab, ToolType } from '~/stores/navigation'
import type { EbeamToolInventoryResponse, EbeamToolRow } from '~/mock-data/ebeam-tool-inventory/ebeam-tool-inventory'

export interface FabToolSummary {
  fab_name: Exclude<Fab, 'all'>
  total: number
  online: number
  offline: number
}

const joinApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const summarizeRowsByFab = (rows: EbeamToolRow[]): FabToolSummary[] => {
  const summaryMap = new Map<Exclude<Fab, 'all'>, FabToolSummary>()

  for (const row of rows) {
    const summary = summaryMap.get(row.fab_name) ?? {
      fab_name: row.fab_name,
      total: 0,
      online: 0,
      offline: 0
    }

    summary.total += 1

    if (row.available === 'On') {
      summary.online += 1
    } else {
      summary.offline += 1
    }

    summaryMap.set(row.fab_name, summary)
  }

  return Array.from(summaryMap.values())
}

export const useEbeamToolApi = () => {
  const config = useRuntimeConfig()
  const inventoryUrl = joinApiPath(config.public.apiBase, '/ebeam/tools')

  const fetchToolInventory = async (): Promise<EbeamToolInventoryResponse> => {
    return await $fetch<EbeamToolInventoryResponse>(inventoryUrl)
  }

  const filterRows = (inventory: EbeamToolInventoryResponse, toolType: ToolType, fab: Fab = 'all'): EbeamToolRow[] => {
    const rows = inventory[toolType]

    if (fab === 'all') {
      return rows
    }

    return rows.filter(row => row.fab_name === fab)
  }

  const fetchToolRows = async (toolType: ToolType, fab: Fab = 'all'): Promise<EbeamToolRow[]> => {
    const inventory = await fetchToolInventory()
    return filterRows(inventory, toolType, fab)
  }

  const fetchFabSummaries = async (toolType: ToolType): Promise<FabToolSummary[]> => {
    const inventory = await fetchToolInventory()
    const rows = filterRows(inventory, toolType)
    return summarizeRowsByFab(rows)
  }

  return {
    fetchToolInventory,
    fetchToolRows,
    fetchFabSummaries,
    filterRows
  }
}
