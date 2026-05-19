import { joinApiPath } from '~/utils/apiPath'

export interface FeatureCount {
  feature: string
  count: number
}

export interface DailyCount {
  date: string
  count: number
}

export interface MeThisMonth {
  requests: number
  days_active: number
}

export interface MeResponse {
  user_id: string
  is_admin: boolean
  this_month: MeThisMonth
  top_features: FeatureCount[]
  daily: DailyCount[]
  first_seen: string | null
  last_seen: string | null
}

export interface SummaryResponse {
  generated_at: string
  dau: number
  wau: number
  mau: number
  top_features_7d: FeatureCount[]
  top_features_30d: FeatureCount[]
}

export interface UserListRow {
  user_id: string
  requests_30d: number
  days_active_30d: number
  last_seen: string | null
  favorite_feature: string | null
}

export interface UserListResponse {
  generated_at: string
  users: UserListRow[]
}

export interface UserHistoryResponse {
  user_id: string
  this_month: MeThisMonth
  top_features: FeatureCount[]
  daily: DailyCount[]
  first_seen: string | null
  last_seen: string | null
}

const ME_KEY = 'activity-me'
const SUMMARY_KEY = 'activity-summary'
const USERS_KEY = 'activity-users'

let inFlightMe: Promise<MeResponse> | null = null
let inFlightSummary: Promise<SummaryResponse> | null = null
let inFlightUsers: Promise<UserListResponse> | null = null

const useActivityUrls = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase
  return {
    meUrl: joinApiPath(base, '/activity/me'),
    summaryUrl: joinApiPath(base, '/activity/summary'),
    usersUrl: joinApiPath(base, '/activity/users'),
    userDetailUrl: (userId: string) =>
      joinApiPath(base, `/activity/users/${encodeURIComponent(userId)}`)
  }
}

export const useActivityMe = () => {
  const { meUrl } = useActivityUrls()
  const fetchOnce = () => {
    if (!inFlightMe) {
      inFlightMe = $fetch<MeResponse>(meUrl).catch((err) => {
        inFlightMe = null
        throw err
      })
    }
    return inFlightMe
  }
  return useAsyncData(ME_KEY, fetchOnce, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}

export const useActivitySummary = () => {
  const { summaryUrl } = useActivityUrls()
  const fetchOnce = () => {
    if (!inFlightSummary) {
      inFlightSummary = $fetch<SummaryResponse>(summaryUrl).catch((err) => {
        inFlightSummary = null
        throw err
      })
    }
    return inFlightSummary
  }
  return useAsyncData(SUMMARY_KEY, fetchOnce, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}

export const useActivityUsers = () => {
  const { usersUrl } = useActivityUrls()
  const fetchOnce = () => {
    if (!inFlightUsers) {
      inFlightUsers = $fetch<UserListResponse>(usersUrl).catch((err) => {
        inFlightUsers = null
        throw err
      })
    }
    return inFlightUsers
  }
  return useAsyncData(USERS_KEY, fetchOnce, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}

// User detail is fetched on-demand (not cached via useAsyncData) because the
// admin clicks individual rows ad hoc; each click is a fresh read.
export const fetchUserHistory = async (userId: string): Promise<UserHistoryResponse> => {
  const { userDetailUrl } = useActivityUrls()
  return await $fetch<UserHistoryResponse>(userDetailUrl(userId))
}

// Reset every cached request so refreshAll triggers real network calls.
export const resetActivityCache = () => {
  inFlightMe = null
  inFlightSummary = null
  inFlightUsers = null
}
