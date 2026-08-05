import type { DailyCount, UserListRow } from '~/composables/useActivityApi'

/** Who a listed person is — the columns the member-directory join touches.
 *  Narrower than `UserListRow` so these read as row-identity helpers rather
 *  than table-wide ones. */
type ListedUser = Pick<UserListRow, 'user_id' | 'emp_nm' | 'dept_nm'>

/** The name the 사용자 column leads with: the member-directory name when the
 *  backend found one, the employee number otherwise (a contractor or service
 *  account with no directory row, or a directory that was unreachable).
 *
 *  The same rule as `identityDisplay.displayName` uses for the header pill,
 *  kept separate because a listed row carries `emp_nm` flat while an identity
 *  nests it under `member`. */
export const userDisplayName = (row: ListedUser): string =>
  row.emp_nm?.trim() || row.user_id

/** The team the 팀 column shows, or a dash when the directory had no team for
 *  this person — an empty cell reads as a rendering bug rather than as an
 *  answer. Matches `activityFeatureLabel`, which dashes the same way. */
export const userTeamLabel = (row: ListedUser): string =>
  row.dept_nm?.trim() || '—'

/** Everything about a person the search box should match — name, employee
 *  number and team, so an admin who knows any one of them can find the row.
 *  Searching a team is how you narrow the table to one org. */
export const userSearchText = (row: ListedUser): string =>
  `${row.emp_nm ?? ''} ${row.user_id} ${row.dept_nm ?? ''}`

// Page-level slugs — see back_dev_home/_logging/feature_map.py, which owns both
// the API-path map and the frontend-path map used by the page-view beacon.
// `cdsem`, `hvsem`, `verity_sem`, `provision` and `thickness` only appear via
// the fallback for pages with no explicit rule — they are real routes, so they
// get real labels rather than the humanize fallback.
const FEATURE_LABELS: Record<string, string> = {
  activity: '사용 통계',
  admin_logs: '운영 로그',
  afm: 'AFM',
  announcements: '공지사항',
  api_tokens: 'API 토큰',
  cdsem: 'CD-SEM',
  chat: 'AI 어시스턴트',
  device_statistics: '디바이스 통계',
  fail_issue: 'Fail Issue',
  hardware: 'Hardware 모니터링',
  health: '서비스 상태',
  home: '홈',
  hvsem: 'HV-SEM',
  live_alarm: 'Live Alarm',
  mag_pixel: 'Mag/Pixel 가이드',
  meas_hist: '측정 이력',
  pm_planning: 'PM Planning',
  provision: 'Provision',
  recipe_search: 'Recipe 검색',
  recipe_tat: 'Recipe TAT',
  sem_list: 'SEM List',
  skew_check: 'Skew Check',
  skewvoir: 'Skewvoir',
  storage: 'Storage',
  thickness: 'Thickness Metrology',
  verity_sem: 'VeritySEM'
}

export const activityFeatureLabel = (feature: string | null | undefined): string => {
  if (!feature) return '—'
  return FEATURE_LABELS[feature]
    ?? feature
      .split('_')
      .filter(Boolean)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ')
}

const sumCounts = (series: DailyCount[]): number =>
  series.reduce((sum, day) => sum + day.count, 0)

export interface PersonalActivityInsights {
  recent7Requests: number
  previous7Requests: number
  activeDays7: number
  averagePerActiveDay30: number
  changePercent: number | null
}

export const summarizePersonalActivity = (series: DailyCount[]): PersonalActivityInsights => {
  const recent7 = series.slice(-7)
  const previous7 = series.slice(-14, -7)
  const recent7Requests = sumCounts(recent7)
  const previous7Requests = sumCounts(previous7)
  const activeDays30 = series.filter(day => day.count > 0).length
  const total30 = sumCounts(series)

  return {
    recent7Requests,
    previous7Requests,
    activeDays7: recent7.filter(day => day.count > 0).length,
    averagePerActiveDay30: activeDays30 > 0 ? Math.round((total30 / activeDays30) * 10) / 10 : 0,
    changePercent: previous7Requests > 0
      ? Math.round(((recent7Requests - previous7Requests) / previous7Requests) * 100)
      : null
  }
}

/** The day page-view ranking began. Rows logged before this are
 *  activity_kind "feature" and are deliberately not backfilled, so a window
 *  reaching further back than this is showing a partial picture and must say
 *  so — an almost-empty ranking otherwise reads as a bug.
 *
 *  DEPLOY STEP: this is the HOME date. Home and office deploy separately, so
 *  the office copy must be reset to the day the office actually deploys —
 *  otherwise the caption claims collection started weeks early and vanishes
 *  while the office ranking is still filling. See
 *  back_dev_home/activity/MIGRATION.md, "Deploy step: PAGE_VIEW_SINCE". */
export const PAGE_VIEW_SINCE = '2026-08-04'

export const pageViewNotice = (
  windowDays: number,
  today: Date
): string | null => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const windowStart = new Date(today.getTime() - (windowDays - 1) * 86_400_000)
  if (windowStart >= since) return null
  return `${PAGE_VIEW_SINCE}부터 페이지 조회 기준으로 집계합니다`
}
