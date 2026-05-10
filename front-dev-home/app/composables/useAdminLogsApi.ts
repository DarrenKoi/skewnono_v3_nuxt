import { joinApiPath } from '~/utils/apiPath'

export interface AdminLogQuery {
  from?: string
  to?: string
  level?: string
  event?: string
  status_min?: string
  status_max?: string
  user_id?: string
  feature?: string
  method?: string
  path?: string
  q?: string
  page?: number
  page_size?: number
}

export interface AdminLogException {
  type?: string | null
  message?: string | null
  stack?: string | null
}

export interface AdminLogItem {
  id: string
  index: string
  timestamp: string | null
  level: string | null
  event: string | null
  logger: string | null
  user_id: string | null
  method: string | null
  path: string | null
  status: number | null
  latency_ms: number | null
  feature: string | null
  message: string | null
  exception: AdminLogException | null
  raw: Record<string, unknown>
}

export interface AdminLogsResponse {
  generated_at: string
  page: number
  page_size: number
  total: number
  filters: Record<string, unknown>
  items: AdminLogItem[]
}

const cleanQuery = (query: AdminLogQuery) => {
  const params: Record<string, string | number> = {}

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params[key] = value
  }

  return params
}

export const useAdminLogsApi = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/admin/logs')

  const fetchLogs = (query: AdminLogQuery): Promise<AdminLogsResponse> => {
    return $fetch<AdminLogsResponse>(url, {
      query: cleanQuery(query)
    })
  }

  return { fetchLogs }
}
