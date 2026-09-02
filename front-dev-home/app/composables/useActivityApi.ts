import { joinApiPath } from '~/utils/apiPath'

export interface FeatureCount {
  feature: string
  count: number
}

/** One day of the 30일 활동 series.
 *
 *  `count` is every request row; `features` breaks down the feature-kind ones
 *  only and is capped, so `other_count` is sent rather than inferred — entry
 *  traffic belongs to no feature, and subtracting a capped list would fold
 *  the dropped features into it. The clicked-day panel names the gap. */
export interface DailyCount {
  date: string
  count: number
  features: FeatureCount[]
  other_count: number
}

/** Only the count is read by the arithmetic helpers, so they say only that —
 *  a test should not have to build a whole day, breakdown included, to check
 *  a sum. */
export type CountedDay = Pick<DailyCount, 'count'>

/** A feature and when this person last opened it. */
export interface FeatureUse {
  feature: string
  at: string
}

export interface MeThisMonth {
  requests: number
  days_active: number
}

export interface MeResponse {
  user_id: string
  is_admin: boolean
  this_month: MeThisMonth
  recent_features: FeatureUse[]
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

export interface FabUsageRow {
  fab: string
  total: number
  pages: FeatureCount[]
}

export interface FabUsageResponse {
  generated_at: string
  fabs_7d: FabUsageRow[]
  fabs_30d: FabUsageRow[]
}

export interface UserListRow {
  user_id: string
  requests_30d: number
  days_active_30d: number
  last_seen: string | null
  /** The feature opened most recently, or null for someone whose only rows
   *  are requests (a page whose beacon never fired, or traffic predating the
   *  page-view rollout). */
  recent_feature: string | null
  /** Member-directory name, joined onto the row in
   *  back_dev_home/activity/routes.py. Null when the directory has no row for
   *  that employee number or could not be reached — the table then shows the
   *  employee number alone. */
  emp_nm: string | null
  /** Member-directory team, from the same join. Nullable independently of
   *  `emp_nm`: a member document may be partial, so a row can carry a name and
   *  no team. */
  dept_nm: string | null
}

export interface UserListResponse {
  generated_at: string
  users: UserListRow[]
}

export interface UserHistoryResponse {
  user_id: string
  this_month: MeThisMonth
  recent_features: FeatureUse[]
  daily: DailyCount[]
  first_seen: string | null
  last_seen: string | null
}

const ME_KEY = 'activity-me'
const SUMMARY_KEY = 'activity-summary'
const USERS_KEY = 'activity-users'
const FABS_KEY = 'activity-fabs'

const meSlot = createInFlightSlot<MeResponse>()
const summarySlot = createInFlightSlot<SummaryResponse>()
const usersSlot = createInFlightSlot<UserListResponse>()
const fabsSlot = createInFlightSlot<FabUsageResponse>()

const useActivityUrls = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase
  return {
    meUrl: joinApiPath(base, '/activity/me'),
    summaryUrl: joinApiPath(base, '/activity/summary'),
    usersUrl: joinApiPath(base, '/activity/users'),
    fabsUrl: joinApiPath(base, '/activity/fabs'),
    userDetailUrl: (userId: string) =>
      joinApiPath(base, `/activity/users/${encodeURIComponent(userId)}`)
  }
}

export const useActivityMe = () => {
  const { meUrl } = useActivityUrls()
  const fetchOnce = () => meSlot.run(() => $fetch<MeResponse>(meUrl))
  return useAsyncData(ME_KEY, fetchOnce, {
    getCachedData: payloadCacheOnInitial
  })
}

export const useActivitySummary = () => {
  const { summaryUrl } = useActivityUrls()
  const fetchOnce = () => summarySlot.run(() => $fetch<SummaryResponse>(summaryUrl))
  return useAsyncData(SUMMARY_KEY, fetchOnce, {
    getCachedData: payloadCacheOnInitial
  })
}

export const useActivityUsers = () => {
  const { usersUrl } = useActivityUrls()
  const fetchOnce = () => usersSlot.run(() => $fetch<UserListResponse>(usersUrl))
  return useAsyncData(USERS_KEY, fetchOnce, {
    getCachedData: payloadCacheOnInitial
  })
}

export const useActivityFabs = () => {
  const { fabsUrl } = useActivityUrls()
  const fetchOnce = () => fabsSlot.run(() => $fetch<FabUsageResponse>(fabsUrl))
  return useAsyncData(FABS_KEY, fetchOnce, {
    getCachedData: payloadCacheOnInitial
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
  meSlot.reset()
  summarySlot.reset()
  usersSlot.reset()
  fabsSlot.reset()
}
