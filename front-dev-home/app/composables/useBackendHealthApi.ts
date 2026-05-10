import { joinApiPath } from '~/utils/apiPath'

const HEALTH_CACHE_KEY = 'backend-health'

export type ServiceStatus = 'up' | 'down'

export interface ServiceHealth {
  id: string
  label: string
  status: ServiceStatus
  latency_ms: number | null
  detail: string
}

export interface ServicesHealthResponse {
  checked_at: string
  services: ServiceHealth[]
}

export const useBackendHealthApi = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/health/services')

  const fetchHealth = async (): Promise<ServicesHealthResponse> => {
    return await $fetch<ServicesHealthResponse>(url)
  }

  return { fetchHealth }
}

// One-shot fetch on page mount; useAsyncData handles SSR/payload reuse.
export const useBackendHealth = () => {
  const { fetchHealth } = useBackendHealthApi()

  return useAsyncData(HEALTH_CACHE_KEY, fetchHealth, {
    default: (): ServicesHealthResponse => ({ checked_at: '', services: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
