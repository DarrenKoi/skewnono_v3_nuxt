import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListResponse, SemListRow } from '~/mock-data/sem-list/sem-list'

export interface FacToolSummary {
  fac_id: Exclude<Fab, 'all'>
  total: number
  online: number
  offline: number
}

const joinApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  if (eqpModelCd.startsWith('CG') || eqpModelCd.startsWith('GT')) return 'cd-sem'
  if (eqpModelCd.startsWith('TP')) return 'hv-sem'
  if (eqpModelCd.startsWith('VERITYSEM')) return 'verity-sem'
  if (eqpModelCd.startsWith('PROVISION')) return 'provision'
  return null
}

export const summarizeRowsByFacId = (rows: SemListRow[]): FacToolSummary[] => {
  const summaryMap = new Map<Exclude<Fab, 'all'>, FacToolSummary>()

  for (const row of rows) {
    const summary = summaryMap.get(row.fac_id) ?? {
      fac_id: row.fac_id,
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

    summaryMap.set(row.fac_id, summary)
  }

  return Array.from(summaryMap.values())
}

export const useSemListApi = () => {
  const config = useRuntimeConfig()
  const semListUrl = joinApiPath(config.public.apiBase, '/sem-list')

  const fetchSemList = async (): Promise<SemListResponse> => {
    return await $fetch<SemListResponse>(semListUrl)
  }

  const filterRows = (rows: SemListRow[], toolType: ToolType, fab: Fab = 'all'): SemListRow[] => {
    return rows.filter((row) => {
      if (classifyToolType(row.eqp_model_cd) !== toolType) return false
      if (fab !== 'all' && row.fac_id !== fab) return false
      return true
    })
  }

  const fetchToolRows = async (toolType: ToolType, fab: Fab = 'all'): Promise<SemListRow[]> => {
    const rows = await fetchSemList()
    return filterRows(rows, toolType, fab)
  }

  const fetchFacSummaries = async (toolType: ToolType): Promise<FacToolSummary[]> => {
    const rows = await fetchSemList()
    return summarizeRowsByFacId(filterRows(rows, toolType))
  }

  return {
    fetchSemList,
    fetchToolRows,
    fetchFacSummaries,
    filterRows
  }
}
