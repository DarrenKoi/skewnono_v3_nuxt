import { joinApiPath } from '~/utils/apiPath'

// Which deployment the SPA is talking to.
//
// Why this is a REQUEST and not a build-time constant, and why the gate is
// cloud rather than office, are both properties of the backend's answer — they
// are written down once, at the endpoint: `back_dev_home/health/routes.py`'s
// `deployment()`. The short version: `ssr: false` bakes `runtimeConfig.public`
// at build time, and the office-built artifact is the one that ships.
//
// The one thing that belongs on this side: it reads `/api/health/deployment`,
// NOT `/api/health/providers`. The providers table is admin-only, and a menu
// that renders correctly only for admins is the bug this exists to avoid.

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
