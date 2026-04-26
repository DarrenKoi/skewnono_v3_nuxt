import type { Fab, ToolType } from '~/stores/navigation'

export interface SemListRow {
  fac_id: string
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: 'HITACHI' | 'AMAT'
  eqp_ip: string
  fab_name: string
  updt_dt: string
  available: 'On' | 'Off'
  version: number
}

export type SemListResponse = SemListRow[]

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

// Sort: R fabs first (ascending), then M fabs (newest fac first — M16 before M11),
// with letter suffixes ascending within the same fac.
export const sortFabNames = (a: string, b: string): number => {
  const parse = (label: string) => {
    const match = label.match(/^([RM])(\d+)([A-Z]?)$/)
    return match ? { prefix: match[1] as 'R' | 'M', num: Number(match[2]), suffix: match[3] ?? '' } : null
  }

  const pa = parse(a)
  const pb = parse(b)
  if (!pa || !pb) return a.localeCompare(b)

  if (pa.prefix !== pb.prefix) return pa.prefix === 'R' ? -1 : 1
  if (pa.num !== pb.num) return pa.prefix === 'R' ? pa.num - pb.num : pb.num - pa.num
  return pa.suffix.localeCompare(pb.suffix)
}

export const extractFabNames = (rows: SemListRow[]): string[] => {
  const names = new Set<string>()
  for (const row of rows) names.add(row.fab_name)
  return Array.from(names).sort(sortFabNames)
}

// device-statistics filters by fac_id, but the URL now carries a fab_name.
// R-class fab_names (R3, R4) all live under fac_id R3; M{n}{A|B|C} → fac_id M{n}.
export const fabNameToFacId = (fabName: string): string => {
  if (fabName.startsWith('R')) return 'R3'
  return fabName.slice(0, 3)
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
      if (fab !== 'all' && row.fab_name !== fab) return false
      return true
    })
  }

  const fetchToolRows = async (toolType: ToolType, fab: Fab = 'all'): Promise<SemListRow[]> => {
    const rows = await fetchSemList()
    return filterRows(rows, toolType, fab)
  }

  const fetchFabNames = async (): Promise<string[]> => {
    const rows = await fetchSemList()
    return extractFabNames(rows)
  }

  return {
    fetchSemList,
    fetchToolRows,
    fetchFabNames,
    filterRows
  }
}
