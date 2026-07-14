import { joinApiPath } from '~/utils/apiPath'

export interface AccessException {
  user_id: string
  granted_at: string | null
}

export interface AccessDeniedAttempt {
  user_id: string
  last_denied_at: string
}

export interface AccessOverview {
  rule: { blocked_prefix: string }
  exceptions: AccessException[]
  denied: AccessDeniedAttempt[]
}

export const useAccessControlApi = () => {
  const config = useRuntimeConfig()
  const overviewUrl = joinApiPath(config.public.apiBase, '/admin/access')
  const exceptionsUrl = joinApiPath(config.public.apiBase, '/admin/access/exceptions')

  const fetchOverview = (): Promise<AccessOverview> => {
    return $fetch<AccessOverview>(overviewUrl)
  }

  const addException = (userId: string): Promise<AccessException> => {
    return $fetch<AccessException>(exceptionsUrl, {
      method: 'POST',
      body: { user_id: userId }
    })
  }

  const removeException = (userId: string): Promise<{ removed: string }> => {
    return $fetch<{ removed: string }>(
      `${exceptionsUrl}/${encodeURIComponent(userId)}`,
      { method: 'DELETE' }
    )
  }

  return { fetchOverview, addException, removeException }
}

// The backend signals a blocked member id with 403 + this error code on
// every /api/* response; app.vue uses it to swap the shell for the denied
// screen. Nuxt may hand us either the raw FetchError (err.data = body) or a
// NuxtError wrapping it (err.data.data = body), so check both shapes.
export const isAccessDeniedError = (err: unknown): boolean => {
  if (!err || typeof err !== 'object') return false
  const data = (err as { data?: unknown }).data as
    | { error?: { code?: string }, data?: { error?: { code?: string } } }
    | undefined
  const code = data?.error?.code ?? data?.data?.error?.code
  return code === 'access_denied'
}
