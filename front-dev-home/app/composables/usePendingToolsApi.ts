import type { PendingToolRow } from '~/utils/pendingToolMatrix'
import { joinApiPath } from '~/utils/apiPath'

// Shared cache key, same convention as SEM_LIST_CACHE_KEY in useSemListApi.ts.
const PENDING_TOOLS_CACHE_KEY = 'pending-tools'

/**
 * The roster tools skewnono cannot reach yet.
 *
 * This composable is used only by `/tool-roster`, so reaching that dedicated
 * route is the user's request to load the full company roster. Fetch on mount,
 * keep the result cached for the session, and expose `execute()` for refresh.
 *
 * The landing page links to the route but never calls this composable, so a
 * landing visit does not touch `v3_df_sem_list`.
 */
export const usePendingTools = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/sem-list/pending')

  return useAsyncData(
    PENDING_TOOLS_CACHE_KEY,
    () => $fetch<PendingToolRow[]>(url),
    {
      immediate: true,
      default: () => [] as PendingToolRow[],
      getCachedData: payloadCacheOnInitial
    }
  )
}
