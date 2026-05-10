import { joinApiPath } from '~/utils/apiPath'

export type Tier = 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond'

export interface TierInfo {
  key: Tier
  label: string
  icon: string
  min_score: number
  next_score: number | null
}

export interface ActivityEvent {
  timestamp: string
  method: string
  path: string
  status: number
  feature: string
}

export interface MeStats {
  score: number
  rank: number
  total_users: number
  streak_days: number
  days_active: number
  favorite_feature: string | null
  by_feature: Record<string, number>
  first_seen: string | null
  last_seen: string | null
}

export interface TierProgress {
  current: TierInfo
  next: TierInfo | null
  score_into_tier: number
  score_to_next: number | null
  pct: number
}

export interface MeResponse {
  user_id: string
  stats: MeStats
  tier: TierProgress
  recent: ActivityEvent[]
}

export interface LeaderRow {
  rank: number
  user_id: string
  score: number
  tier: Tier
  streak_days: number
  is_me: boolean
}

export interface LeaderboardResponse {
  generated_at: string
  me: LeaderRow | null
  top: LeaderRow[]
}

const ME_KEY = 'activity-me'
const LB_KEY = 'activity-leaderboard'

export const useActivityApi = () => {
  const config = useRuntimeConfig()
  const meUrl = joinApiPath(config.public.apiBase, '/activity/me')
  const lbUrl = joinApiPath(config.public.apiBase, '/activity/leaderboard')

  const fetchMe = async (): Promise<MeResponse> => $fetch<MeResponse>(meUrl)
  const fetchLeaderboard = async (): Promise<LeaderboardResponse> => $fetch<LeaderboardResponse>(lbUrl)

  return { fetchMe, fetchLeaderboard }
}

export const useActivityMe = () => {
  const { fetchMe } = useActivityApi()
  return useAsyncData(ME_KEY, fetchMe, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}

export const useActivityLeaderboard = () => {
  const { fetchLeaderboard } = useActivityApi()
  return useAsyncData(LB_KEY, fetchLeaderboard, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
