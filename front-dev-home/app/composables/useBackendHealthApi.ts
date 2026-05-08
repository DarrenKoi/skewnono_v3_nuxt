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

// Polls /api/health/services every 15s. The cadence is a compromise — fast
// enough that a downed service shows up within a glance, slow enough that the
// endpoint stays cheap. Pauses while the tab is hidden.
export const useBackendHealth = () => {
  const { fetchHealth } = useBackendHealthApi()

  const result = useAsyncData(HEALTH_CACHE_KEY, fetchHealth, {
    default: (): ServicesHealthResponse => ({ checked_at: '', services: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })

  let timer: ReturnType<typeof setInterval> | null = null

  const startTimer = () => {
    if (timer) return
    timer = setInterval(() => {
      result.refresh()
    }, 15_000)
  }

  const stopTimer = () => {
    if (!timer) return
    clearInterval(timer)
    timer = null
  }

  const onVisibility = () => {
    if (document.hidden) {
      stopTimer()
    } else {
      result.refresh()
      startTimer()
    }
  }

  onMounted(() => {
    startTimer()
    document.addEventListener('visibilitychange', onVisibility)
  })

  onBeforeUnmount(() => {
    stopTimer()
    document.removeEventListener('visibilitychange', onVisibility)
  })

  return result
}
