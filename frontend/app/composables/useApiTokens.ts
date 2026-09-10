import { joinApiPath } from '~/utils/apiPath'

const TOKENS_CACHE_KEY = 'api-tokens'

export interface ApiTokenRow {
  id: string
  label: string
  created_at: string
  last_used_at: string | null
}

interface ListResponse {
  tokens: ApiTokenRow[]
}

interface CreateResponse {
  token: ApiTokenRow
  plaintext: string
}

export const useApiTokens = () => {
  const config = useRuntimeConfig()
  const base = joinApiPath(config.public.apiBase, '/account/api-tokens')

  const fetchList = async (): Promise<ApiTokenRow[]> => {
    const res = await $fetch<ListResponse>(base)
    return res.tokens
  }

  const { data, pending, error, refresh } = useAsyncData(
    TOKENS_CACHE_KEY,
    fetchList,
    { default: () => [] as ApiTokenRow[] }
  )

  const create = async (label: string): Promise<CreateResponse> => {
    const res = await $fetch<CreateResponse>(base, {
      method: 'POST',
      body: { label }
    })
    data.value = [res.token, ...(data.value ?? [])]
    return res
  }

  const revoke = async (id: string): Promise<void> => {
    await $fetch(`${base}/${id}`, { method: 'DELETE' })
    data.value = (data.value ?? []).filter(t => t.id !== id)
  }

  return { tokens: data, pending, error, refresh, create, revoke }
}
