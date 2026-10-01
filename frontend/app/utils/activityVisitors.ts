import type { EChartsOption } from 'echarts'
import { userDisplayName, userTeamLabel } from './activity.ts'
import { CHART_AXIS_LABEL, CHART_LEGEND_LABEL } from './chartType.ts'
import type { DailyVisitors, UserListRow } from '~/composables/useActivityApi'

/**
 * The admin 방문자 분석 page's arithmetic and its trend chart's ECharts option,
 * built without importing echarts — same reason as activitySparkline.ts:
 * `npm test` runs this under `node --test`.
 */

export type VisitorWindowKey = '2w' | '1m' | '2m'

const WINDOW_DAYS: Record<VisitorWindowKey, number> = { '2w': 14, '1m': 30, '2m': 60 }

export const VISITOR_WINDOW_TABS: { label: string, value: VisitorWindowKey }[] = [
  { label: '2주', value: '2w' },
  { label: '1개월', value: '1m' },
  { label: '2개월', value: '2m' }
]

/**
 * The most recent days of the series. The backend sends its whole 60-day
 * window once and every tab is a slice of it, so switching costs no request.
 */
export const visitorWindow = (
  series: readonly DailyVisitors[],
  key: VisitorWindowKey
): DailyVisitors[] => series.slice(-WINDOW_DAYS[key])

const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토']

/** '2026-10-02' → '10.02'. The year is on the tooltip; the axis has no room for it. */
export const visitorAxisLabel = (iso: string): string => iso.slice(5).replace('-', '.')

const people = (count: number): string => `${count.toLocaleString()}명`

// The weekday is named because it is the first thing the shape raises: a dip
// every seven bars is a weekend, not a problem.
export const visitorTooltip = (day: DailyVisitors): string => {
  const weekday = DAY_NAMES[new Date(`${day.date}T00:00:00Z`).getUTCDay()]
  return `${day.date}${weekday ? ` (${weekday})` : ''}`
    + `<br>DAU ${people(day.visitors)} · WAU ${people(day.wau)} · MAU ${people(day.mau)}`
}

/**
 * DAU as bars, rolling WAU and MAU as lines, on one axis.
 *
 * One axis on purpose: all three count the same thing, people, so the gap
 * between a bar and the MAU line IS the answer to "how many of our monthly
 * users came today". A second axis would let the two be scaled apart and
 * erase that.
 */
export const buildVisitorsOption = (series: readonly DailyVisitors[]): EChartsOption => ({
  grid: { left: 44, right: 12, top: 36, bottom: 28 },
  legend: { top: 0, right: 0, textStyle: CHART_LEGEND_LABEL },
  tooltip: {
    // 'axis' so the whole column is the hit target — a one-visitor day is a
    // sliver of a bar next to a busy one.
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      const day = series[(first as { dataIndex?: number } | undefined)?.dataIndex ?? -1]
      return day ? visitorTooltip(day) : ''
    }
  },
  xAxis: {
    type: 'category',
    data: series.map(day => day.date),
    axisTick: { show: false },
    axisLabel: { ...CHART_AXIS_LABEL, formatter: visitorAxisLabel }
  },
  yAxis: {
    type: 'value',
    min: 0,
    minInterval: 1,
    axisLabel: CHART_AXIS_LABEL
  },
  series: [
    {
      name: 'DAU',
      type: 'bar',
      data: series.map(day => day.visitors),
      barCategoryGap: '30%',
      itemStyle: { borderRadius: [2, 2, 0, 0] }
    },
    // No point symbols: sixty dots per line is noise, and the axis tooltip
    // already reads every series at the hovered column.
    { name: 'WAU', type: 'line', data: series.map(day => day.wau), showSymbol: false },
    { name: 'MAU', type: 'line', data: series.map(day => day.mau), showSymbol: false }
  ]
})

/** DAU ÷ MAU as a whole percent — of the people who came this month, how many
 *  came today. Null when the month is empty, which is "no answer", not 0%. */
export const stickinessPercent = (
  day: Pick<DailyVisitors, 'visitors' | 'mau'> | undefined
): number | null =>
  day && day.mau > 0 ? Math.round((day.visitors * 100) / day.mau) : null

/** One row of a CountBarList: a name, an optional second line, a number. */
export interface CountRow {
  label: string
  hint?: string
  count: number
}

type Visitor = Pick<UserListRow, 'user_id' | 'emp_nm' | 'dept_nm' | 'days_active_30d' | 'requests_30d'>

/** Who comes most often: active days first, because "often" is about showing
 *  up — one heavy afternoon is a lot of requests and a single visit. */
export const frequentVisitors = (users: readonly Visitor[], cap = 10): CountRow[] =>
  [...users]
    .sort((left, right) =>
      right.days_active_30d - left.days_active_30d
      || right.requests_30d - left.requests_30d
      || left.user_id.localeCompare(right.user_id)
    )
    .slice(0, cap)
    .map(row => ({
      label: userDisplayName(row),
      hint: userTeamLabel(row),
      count: row.days_active_30d
    }))

// [upper bound in active days, label, what that habit looks like]
const FREQUENCY_BANDS: [number, string, string][] = [
  [1, '1일', '한 번 들른 사용자'],
  [5, '2–5일', '가끔'],
  [15, '6–15일', '주 2–3회'],
  [Infinity, '16일 이상', '거의 매일']
]

/** How the month's users split by habit. Every band is returned, empty or not. */
export const visitFrequencyBuckets = (users: readonly Visitor[]): CountRow[] => {
  const counts = FREQUENCY_BANDS.map(() => 0)
  for (const row of users) {
    const band = FREQUENCY_BANDS.findIndex(([upper]) => row.days_active_30d <= upper)
    counts[band] = (counts[band] ?? 0) + 1
  }
  return FREQUENCY_BANDS.map(([, label, hint], index) => ({ label, hint, count: counts[index] ?? 0 }))
}

const NO_TEAM = '소속 미확인'

/** People per team, largest first. A person the directory had no team for is
 *  counted under a named bucket rather than dropped — the totals must add up
 *  to the user count beside them. */
export const visitorsByTeam = (users: readonly Visitor[]): CountRow[] => {
  const counts = new Map<string, number>()
  for (const row of users) {
    const team = row.dept_nm?.trim() || NO_TEAM
    counts.set(team, (counts.get(team) ?? 0) + 1)
  }
  return [...counts]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) =>
      right.count - left.count
      // A named team wins a tie against the unknown bucket; collation alone
      // would file Hangul ahead of a Latin team name.
      || Number(left.label === NO_TEAM) - Number(right.label === NO_TEAM)
      || left.label.localeCompare(right.label, 'ko')
    )
}
