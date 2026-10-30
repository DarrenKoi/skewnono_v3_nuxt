import type { EChartsOption } from 'echarts'
import { userDisplayName, userTeamLabel } from './activity.ts'
import { dayHeading, visitorAxisLabel, type CountRow } from './activityVisitors.ts'
import { CHART_AXIS_LABEL } from './chartType.ts'
import type { DailyRequests, RequestWindow, UserListRow } from '~/composables/useActivityApi'

/**
 * The admin 요청 분석 page's arithmetic and its trend chart's ECharts option,
 * built without importing echarts so `npm test` can run it under `node --test`.
 * The 2주…3개월 slicing is `visitorWindow`, shared with 방문자 분석.
 */

const sum = (days: readonly DailyRequests[]): number =>
  days.reduce((total, day) => total + day.requests, 0)

/** Requests per active person-day, one decimal — "on a day someone used the
 *  site, how many requests did they make". Null when nobody came, which is
 *  "no answer", not zero. */
export const requestsPerPersonDay = (days: readonly DailyRequests[]): number | null => {
  const personDays = days.reduce((total, day) => total + day.users, 0)
  return personDays > 0 ? Math.round((sum(days) * 10) / personDays) / 10 : null
}

/** The KPI row, all from the one day series so no card can disagree with the
 *  chart under it. */
export const requestKpis = (days: readonly DailyRequests[]) => {
  const perPersonDay = requestsPerPersonDay(days.slice(-30))
  return [
    {
      label: '오늘 요청',
      value: (days[days.length - 1]?.requests ?? 0).toLocaleString(),
      hint: '오늘 0시(KST)부터 지금까지',
      icon: 'i-lucide-activity',
      color: 'text-(--sk-accent)'
    },
    {
      label: '7D 요청',
      value: sum(days.slice(-7)).toLocaleString(),
      hint: '오늘 포함 최근 7일',
      icon: 'i-lucide-calendar-range',
      color: 'text-emerald-500'
    },
    {
      label: '30D 요청',
      value: sum(days.slice(-30)).toLocaleString(),
      hint: '오늘 포함 최근 30일',
      icon: 'i-lucide-mouse-pointer-click',
      color: 'text-amber-500'
    },
    {
      label: '1인·1일당 요청',
      value: perPersonDay === null ? '—' : perPersonDay.toLocaleString(),
      hint: '30일 요청 ÷ 사용자·활동일',
      icon: 'i-lucide-user-round',
      color: 'text-violet-500'
    }
  ]
}

const count = (value: number, unit: string): string => `${value.toLocaleString()}${unit}`

export const requestTooltip = (day: DailyRequests): string =>
  dayHeading(day.date) + `<br>요청 ${count(day.requests, '건')} · 요청자 ${count(day.users, '명')}`

/** One bar per KST day. The requester count rides in the tooltip rather than
 *  as a second series: hundreds of requests over a handful of people on one
 *  axis flattens the people line, and a second axis invites reading the two
 *  as comparable. */
export const buildRequestsOption = (series: readonly DailyRequests[]): EChartsOption => ({
  grid: { left: 52, right: 12, top: 12, bottom: 28 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      const day = series[(first as { dataIndex?: number } | undefined)?.dataIndex ?? -1]
      return day ? requestTooltip(day) : ''
    }
  },
  xAxis: {
    type: 'category',
    data: series.map(day => day.date),
    axisTick: { show: false },
    axisLabel: { ...CHART_AXIS_LABEL, formatter: visitorAxisLabel }
  },
  yAxis: { type: 'value', min: 0, minInterval: 1, axisLabel: CHART_AXIS_LABEL },
  series: [{
    name: '요청',
    type: 'bar',
    data: series.map(day => day.requests),
    barCategoryGap: '30%',
    itemStyle: { borderRadius: [2, 2, 0, 0] }
  }]
})

/** What the feature list leaves out, said under it so the list is not read as
 *  the window's whole volume. Null when there is nothing left out. */
export const requestRemainderNote = (window: RequestWindow | undefined): string | null => {
  if (!window) return null
  const parts = [
    window.entry > 0 ? `장비 목록 진입 ${count(window.entry, '건')}` : null,
    window.other_count > 0 ? `Top 10 밖 기능 ${count(window.other_count, '건')}` : null
  ].filter(Boolean)
  return parts.length ? `목록 외: ${parts.join(' · ')}` : null
}

type Requester = Pick<UserListRow, 'user_id' | 'emp_nm' | 'dept_nm' | 'requests_30d'>

/** Everyone, most requests first; ties by employee number so the order is
 *  stable across refreshes. */
export const topRequesters = (users: readonly Requester[]): CountRow[] =>
  [...users]
    .sort((left, right) => right.requests_30d - left.requests_30d || left.user_id.localeCompare(right.user_id))
    .map(row => ({ label: userDisplayName(row), hint: userTeamLabel(row), count: row.requests_30d }))
