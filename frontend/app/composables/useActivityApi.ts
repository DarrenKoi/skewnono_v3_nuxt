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

/** One calendar day of page opens (KST), independent of request volume. */
export type VisitCount = Pick<DailyCount, 'date' | 'count'>

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
  visits: VisitCount[]
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
   *  backend/activity/routes.py. Null when the directory has no row for
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

/** Page opens under one tool family. `family` is the backend's registry slug
 *  (`cdsem`, not `cd-sem`). Both numbers count page views: `total` is
 *  the distinct people who opened a page of the family — not a DAU-style
 *  active-user count, and not additive across families. */
export interface FamilyUsageRow {
  family: string
  total: number
  pages: FeatureCount[]
}

/** Every family, in the backend's registry order, zero rows included. */
export interface FamilyUsageResponse {
  generated_at: string
  families_7d: FamilyUsageRow[]
  families_30d: FamilyUsageRow[]
}

/** How many distinct people were active on, and up to, one KST day.
 *
 *  `visitors` is that day alone (DAU). `wau` and `mau` are the distinct people
 *  over the 7 and 30 days ending that day — sent rather than derived, because
 *  days are not additive: someone active on two days is counted in both. The
 *  last entry equals `SummaryResponse`'s `dau`, `wau` and `mau`. */
export interface DailyVisitors {
  date: string
  visitors: number
  wau: number
  mau: number
}

/** 60 consecutive KST days, oldest first, today last. Admin-only. */
export interface VisitorsResponse {
  generated_at: string
  days: DailyVisitors[]
}

export interface UserHistoryResponse {
  user_id: string
  this_month: MeThisMonth
  recent_features: FeatureUse[]
  daily: DailyCount[]
  visits: VisitCount[]
  first_seen: string | null
  last_seen: string | null
}

const ME_KEY = 'activity-me'
const SUMMARY_KEY = 'activity-summary'
const USERS_KEY = 'activity-users'
const FABS_KEY = 'activity-fabs'
const FAMILIES_KEY = 'activity-families'
const VISITORS_KEY = 'activity-visitors'

const meSlot = createInFlightSlot<MeResponse>()
const summarySlot = createInFlightSlot<SummaryResponse>()
const usersSlot = createInFlightSlot<UserListResponse>()
const fabsSlot = createInFlightSlot<FabUsageResponse>()
const familiesSlot = createInFlightSlot<FamilyUsageResponse>()
const visitorsSlot = createInFlightSlot<VisitorsResponse>()

const useActivityUrls = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase
  return {
    meUrl: joinApiPath(base, '/activity/me'),
    summaryUrl: joinApiPath(base, '/activity/summary'),
    usersUrl: joinApiPath(base, '/activity/users'),
    fabsUrl: joinApiPath(base, '/activity/fabs'),
    familiesUrl: joinApiPath(base, '/activity/families'),
    visitorsUrl: joinApiPath(base, '/activity/visitors'),
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

export const useActivityFamilies = () => {
  const { familiesUrl } = useActivityUrls()
  const fetchOnce = () => familiesSlot.run(() => $fetch<FamilyUsageResponse>(familiesUrl))
  return useAsyncData(FAMILIES_KEY, fetchOnce, {
    getCachedData: payloadCacheOnInitial
  })
}

export const useActivityVisitors = () => {
  const { visitorsUrl } = useActivityUrls()
  const fetchOnce = () => visitorsSlot.run(() => $fetch<VisitorsResponse>(visitorsUrl))
  return useAsyncData(VISITORS_KEY, fetchOnce, {
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
  familiesSlot.reset()
  visitorsSlot.reset()
}
