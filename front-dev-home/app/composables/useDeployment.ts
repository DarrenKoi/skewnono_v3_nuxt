import { joinApiPath } from '~/utils/apiPath'

// Which deployment the SPA is talking to.
//
// The SPA cannot answer this by itself. `ssr: false` bakes
// `runtimeConfig.public` at BUILD time, and the artifact built at the office is
// byte-for-byte the one `scripts/deploy/pack.py` ships to the cloud — so a
// build-time flag would be a step someone has to remember on every pack, and
// forgetting it fails in the silent direction. The backend answers instead,
// from `_runtime/env.py`'s `is_cloud()`, which is a filesystem-path check and
// so cannot be flipped by a stray environment variable.
//
// Cloud, NOT office. Phase 2 runs on a company localhost against real data,
// which is exactly where an unvalidated page has to be exercised — only the
// Phase 3 production deploy hides anything.
//
// Reads `/api/health/deployment`, NOT `/api/health/providers`: the providers
// table is admin-only, and a menu that renders correctly only for admins is
// the bug this would be written to avoid.

export interface DeploymentResponse {
  is_cloud: boolean
}

/**
 * `isCloud`. Defaults to FALSE while the answer is unknown — loading, offline,
 * or an older backend that 404s this endpoint.
 *
 * That default is the safer of the two. Guessing "not cloud" at worst leaves a
 * BETA row visible to a production user, who is welcome to open it anyway —
 * the routes are deliberately never blocked. Guessing "cloud" would delete the
 * only entry point to those pages on the machines where they are being built,
 * every time the request was slow.
 *
 * One cache key for the whole app: the answer is a property of the instance,
 * so two callers can never legitimately disagree and must not fetch twice.
 */
export const useDeployment = () => {
  const config = useRuntimeConfig()

  const { data } = useAsyncData(
    'deployment',
    () => $fetch<DeploymentResponse>(
      joinApiPath(config.public.apiBase, '/health/deployment')
    ),
    {
      default: (): DeploymentResponse | null => null,
      getCachedData: payloadCache
    }
  )

  return { isCloud: computed(() => data.value?.is_cloud === true) }
}
