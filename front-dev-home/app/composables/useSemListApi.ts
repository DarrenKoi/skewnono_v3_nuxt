import type { Fab, ToolType } from '~/stores/navigation'
import { joinApiPath } from '~/utils/apiPath'
import { NO_FAB, hasFab, normalizeFab } from '~/utils/fab'

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
  // Free-form string (digits + letters), e.g. '1A'; '' when unknown.
  version: string
}

export type SemListResponse = SemListRow[]

export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  if (eqpModelCd.startsWith('CG') || eqpModelCd.startsWith('GT')) return 'cd-sem'
  if (eqpModelCd.startsWith('TP')) return 'hv-sem'
  if (eqpModelCd.startsWith('VERITYSEM')) return 'verity-sem'
  if (eqpModelCd.startsWith('PROVISION')) return 'provision'
  return null
}

export const useSemListApi = () => {
  const config = useRuntimeConfig()
  const semListUrl = joinApiPath(config.public.apiBase, '/sem-list')

  const fetchSemList = async (): Promise<SemListResponse> => {
    return await $fetch<SemListResponse>(semListUrl)
  }

  const filterRows = (rows: SemListRow[], toolType: ToolType, fab: Fab = NO_FAB): SemListRow[] => {
    // Normalized once, not per row: row.fab_name carries whatever casing its source DB used,
    // so the comparison has to be case-insensitive — a raw `===` empties the whole list.
    const target = hasFab(fab) ? normalizeFab(fab) : ''
    return rows.filter((row) => {
      if (classifyToolType(row.eqp_model_cd) !== toolType) return false
      if (target !== '' && normalizeFab(row.fab_name) !== target) return false
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
