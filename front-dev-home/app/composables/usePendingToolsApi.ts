import type { PendingToolRow } from '~/utils/pendingToolMatrix'
import { joinApiPath } from '~/utils/apiPath'

// Shared cache key, same convention as SEM_LIST_CACHE_KEY in useSemListApi.ts.
const PENDING_TOOLS_CACHE_KEY = 'pending-tools'

/**
 * The roster tools skewnono cannot reach yet — fetched ON DEMAND ONLY.
 *
 * `immediate: false` is the point, not an optimization. `v3_df_sem_list` is the
 * full company roster and is only wanted when someone is actually preparing a
 * firewall request, so navigating to the page must not touch it. Call
 * `execute()` from a user action; the result then stays cached for the session
 * and `execute()` again re-fetches.
 *
 * Deliberately unlike `useSemList()`, which fetches on mount because five other
 * features depend on the roster being warm.
 */
export const usePendingTools = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/sem-list/pending')

  return useAsyncData(
    PENDING_TOOLS_CACHE_KEY,
    () => $fetch<PendingToolRow[]>(url),
    { immediate: false, default: () => [] as PendingToolRow[] }
  )
}
