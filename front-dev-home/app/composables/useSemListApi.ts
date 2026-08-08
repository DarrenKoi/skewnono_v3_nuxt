import type { Fab, ToolType } from '~/stores/navigation'
import { joinApiPath } from '~/utils/apiPath'
import { NO_FAB, hasFab, normalizeFab } from '~/utils/fab'
import { classifyToolType } from '~/utils/toolType'

// One shared cache key for /api/sem-list. Every consumer (hub page, tool-type
// tabs, fab sidebar, inventory view) calls useSemList() and derives its view
// via computed.
const SEM_LIST_CACHE_KEY = 'sem-list'

// Module-scoped in-flight promise so concurrent useAsyncData calls from
// sibling components (which mount across separate Suspense boundaries in
// ssr:false mode) collapse into a single network request. Nuxt's built-in
// _asyncDataPromises dedup is keyed per call site and doesn't reliably
// cover this layout-vs-page race in client-only rendering.
const semListSlot = createInFlightSlot<SemListResponse>()

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

export const useSemListApi = () => {
  const config = useRuntimeConfig()
  const semListUrl = joinApiPath(config.public.apiBase, '/sem-list')

  const fetchSemList = async (): Promise<SemListResponse> => {
    return await $fetch<SemListResponse>(semListUrl)
  }

  const filterRows = (rows: SemListRow[], toolType: ToolType, fab: Fab | readonly Fab[] = NO_FAB): SemListRow[] => {
    // Normalized once, not per row: row.fab_name carries whatever casing its source DB used,
    // so the comparison has to be case-insensitive — a raw `===` empties the whole list.
    // An empty target set means "no fab filter".
    const list = Array.isArray(fab) ? fab : [fab]
    const targets = new Set(list.filter(hasFab).map(normalizeFab))
    return rows.filter((row) => {
      if (classifyToolType(row.eqp_model_cd) !== toolType) return false
      if (targets.size > 0 && !targets.has(normalizeFab(row.fab_name))) return false
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
  const fetchOnce = () => semListSlot.run(fetchSemList)
  return useAsyncData(SEM_LIST_CACHE_KEY, fetchOnce, {
    default: () => [] as SemListRow[],
    getCachedData: payloadCache
  })
}
