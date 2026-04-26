import type { Fab, ToolType } from '~/stores/navigation'

// One shared cache key for /api/sem-list. Every consumer (hub page, tool-type
// tabs, fab sidebar, inventory view) calls useSemList() and derives its view
// via computed.
const SEM_LIST_CACHE_KEY = 'sem-list'

// Module-scoped in-flight promise so concurrent useAsyncData calls from
// sibling components (which mount across separate Suspense boundaries in
// ssr:false mode) collapse into a single network request. Nuxt's built-in
// _asyncDataPromises dedup is keyed per call site and doesn't reliably
// cover this layout-vs-page race in client-only rendering.
let inFlightSemList: Promise<SemListResponse> | null = null

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

  return {
    fetchSemList,
    filterRows
  }
}

export const useSemList = () => {
  const { fetchSemList } = useSemListApi()
  const fetchOnce = () => {
    if (!inFlightSemList) {
      inFlightSemList = fetchSemList().catch((err) => {
        inFlightSemList = null
        throw err
      })
    }
    return inFlightSemList
  }
  return useAsyncData(SEM_LIST_CACHE_KEY, fetchOnce, {
    default: () => [] as SemListRow[],
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
