import type { EChartsOption } from 'echarts'
import { byActiveDays, userDisplayName, userTeamLabel } from './activity.ts'
import { DAY_NAMES } from './activityCalendar.ts'
import { CHART_AXIS_LABEL } from './chartType.ts'
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

export type VisitorMetricKey = 'dau' | 'wau' | 'mau'

export const VISITOR_METRIC_TABS: { label: string, value: VisitorMetricKey }[] = [
  { label: 'DAU', value: 'dau' },
  { label: 'WAU', value: 'wau' },
  { label: 'MAU', value: 'mau' }
]

const METRIC_VALUE: Record<VisitorMetricKey, (day: DailyVisitors) => number> = {
  dau: day => day.visitors,
  wau: day => day.wau,
  mau: day => day.mau
}

/**
 * One metric per chart: DAU as bars, rolling WAU or MAU as a line.
 *
 * One at a time on purpose. Drawn together on a shared axis, DAU was a row of
 * slivers under the MAU line and its day-to-day movement could not be read.
 * The tooltip still names all three for the hovered day.
 */
export const buildVisitorsOption = (
  series: readonly DailyVisitors[],
  metric: VisitorMetricKey = 'dau'
): EChartsOption => ({
  grid: { left: 44, right: 12, top: 12, bottom: 28 },
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
    // Bars are read by length, so they start at zero. A rolling count moves a
    // few people on a base of hundreds: from zero that line is flat, so its
    // axis fits the data instead.
    ...(metric === 'dau' ? { min: 0 } : { scale: true }),
    minInterval: 1,
    axisLabel: CHART_AXIS_LABEL
  },
  series: [
    metric === 'dau'
      ? {
          name: 'DAU',
          type: 'bar',
          data: series.map(METRIC_VALUE.dau),
          barCategoryGap: '30%',
          itemStyle: { borderRadius: [2, 2, 0, 0] }
        }
      // No point symbols: sixty dots on the line is noise, and the axis
      // tooltip already reads the hovered column.
      : {
          name: metric.toUpperCase(),
          type: 'line',
          data: series.map(METRIC_VALUE[metric]),
          showSymbol: false
        }
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
  /** Hover text, for a label that abbreviates something (a feature slug). */
  title?: string
  count: number
}

type Visitor = Pick<UserListRow, 'user_id' | 'emp_nm' | 'dept_nm' | 'days_active_30d' | 'requests_30d'>

/** Everyone, most frequent visitor first (see `byActiveDays`). The list that
 *  shows it decides how many rows to draw. */
export const frequentVisitors = (users: readonly Visitor[]): CountRow[] =>
  [...users].sort(byActiveDays).map(row => ({
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
