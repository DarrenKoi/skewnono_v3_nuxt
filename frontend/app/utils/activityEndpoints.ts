import type { EChartsOption } from 'echarts'
import { userDisplayName, userTeamLabel } from './activity.ts'
import { dayHeading, visitorAxisLabel, type CountRow } from './activityVisitors.ts'
import { CHART_AXIS_LABEL } from './chartType.ts'
import { escapeHtml } from './html.ts'
import type { EndpointDay, EndpointsResponse } from '~/composables/useActivityApi'

/**
 * The admin 엔드포인트 분석 page's arithmetic and its stacked trend chart,
 * built without importing echarts so `npm test` can run it under `node --test`.
 * Every window is a slice of the one 90-day series (`visitorWindow`).
 */

export const OTHER_ENDPOINTS = '기타'
export const OTHER_CALLERS = '기타 (미식별 포함)'
export const UNATTRIBUTED = '미식별 (사번 없음)'
const CHART_SERIES = 5

const sumRequests = (days: readonly EndpointDay[]): number =>
  days.reduce((total, day) => total + day.requests, 0)

const sumBy = (days: readonly EndpointDay[], pick: (day: EndpointDay) => Record<string, number>) => {
  const totals = new Map<string, number>()
  for (const day of days) {
    for (const [key, count] of Object.entries(pick(day))) totals.set(key, (totals.get(key) ?? 0) + count)
  }
  // Most first; ties by name so the order is stable across refreshes.
  return [...totals].sort(([a, x], [b, y]) => y - x || a.localeCompare(b))
}

/** "GET /api/x" → label "/api/x", hint "GET". */
const endpointRow = (key: string, count: number): CountRow => {
  const space = key.indexOf(' ')
  return space < 0
    ? { label: key, count }
    : { label: key.slice(space + 1), hint: key.slice(0, space), title: key, count }
}

export const topEndpoints = (days: readonly EndpointDay[]): CountRow[] =>
  sumBy(days, day => day.endpoints).map(([key, count]) => endpointRow(key, count))

/** Callers, most calls first. Calls with no user_id (health probes, calls
 *  before identity ran) are one row of their own, ranked like the rest, so a
 *  large unattributed share is visible instead of silently missing. */
const memberOf = (userId: string, names: EndpointsResponse['names']) =>
  ({ user_id: userId, emp_nm: names[userId]?.emp_nm ?? null, dept_nm: names[userId]?.dept_nm ?? null })

export const topCallers = (
  days: readonly EndpointDay[],
  names: EndpointsResponse['names']
): CountRow[] => {
  const rows: CountRow[] = sumBy(days, day => day.users).map(([userId, count]) => {
    const member = memberOf(userId, names)
    return { label: userDisplayName(member), hint: userTeamLabel(member), count }
  })
  const attributed = rows.reduce((total, row) => total + row.count, 0)
  const unattributed = sumRequests(days) - attributed
  if (unattributed > 0) rows.push({ label: UNATTRIBUTED, count: unattributed })
  return rows.sort((a, b) => b.count - a.count)
}

export const endpointKpis = (days: readonly EndpointDay[]) => [
  {
    label: '오늘 호출',
    value: (days[days.length - 1]?.requests ?? 0).toLocaleString(),
    hint: '오늘 0시(KST)부터 지금까지',
    icon: 'i-lucide-activity'
  },
  {
    label: '7D 호출',
    value: sumRequests(days.slice(-7)).toLocaleString(),
    hint: '오늘 포함 최근 7일',
    icon: 'i-lucide-calendar-range'
  },
  {
    label: '30D 호출',
    value: sumRequests(days.slice(-30)).toLocaleString(),
    hint: '오늘 포함 최근 30일',
    icon: 'i-lucide-calendar'
  },
  {
    label: '30D 일평균',
    value: Math.round(sumRequests(days.slice(-30)) / Math.max(1, Math.min(30, days.length))).toLocaleString(),
    hint: '최근 30일 호출 ÷ 30',
    icon: 'i-lucide-gauge'
  }
].map(kpi => ({ ...kpi, color: 'text-(--sk-ink-muted)' }))

export type TrendAxis = 'endpoints' | 'users'

export const TREND_AXIS_TABS: { label: string, value: TrendAxis }[] = [
  { label: '엔드포인트별', value: 'endpoints' },
  { label: '사용자별', value: 'users' }
]

/** The window's top five endpoints (or callers) as stacked bars, the rest as
 *  one band, so each bar's height is still that day's whole call count. For
 *  callers the rest includes calls with no user, which no top band can hold. */
export const buildEndpointsOption = (
  series: readonly EndpointDay[],
  axis: TrendAxis = 'endpoints',
  names: EndpointsResponse['names'] = {}
): EChartsOption => {
  const pick = (day: EndpointDay) => (axis === 'endpoints' ? day.endpoints : day.users)
  const top = sumBy(series, pick).slice(0, CHART_SERIES).map(([key]) => key)
  const label = (key: string) => (axis === 'endpoints' ? key : userDisplayName(memberOf(key, names)))
  const bands = [
    ...top.map(key => ({ name: label(key), data: series.map(day => pick(day)[key] ?? 0) })),
    {
      name: axis === 'endpoints' ? OTHER_ENDPOINTS : OTHER_CALLERS,
      data: series.map(day => day.requests - top.reduce((total, key) => total + (pick(day)[key] ?? 0), 0))
    }
  ]
  return {
    grid: { left: 56, right: 12, top: 40, bottom: 28 },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 11 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const list = (Array.isArray(params) ? params : [params]) as { dataIndex?: number, seriesName?: string, value?: unknown, marker?: string }[]
        const day = series[list[0]?.dataIndex ?? -1]
        if (!day) return ''
        // Escaped: a Flask rule's <tool_slug> would otherwise be parsed as a
        // tag by the tooltip's innerHTML and vanish from the path.
        const lines = list
          .filter(item => Number(item.value) > 0)
          .map(item => `${item.marker ?? ''}${escapeHtml(item.seriesName ?? '')} ${Number(item.value).toLocaleString()}건`)
        return `${dayHeading(day.date)} · 전체 ${day.requests.toLocaleString()}건<br>${lines.join('<br>')}`
      }
    },
    xAxis: {
      type: 'category',
      data: series.map(day => day.date),
      axisTick: { show: false },
      axisLabel: { ...CHART_AXIS_LABEL, formatter: visitorAxisLabel }
    },
    yAxis: { type: 'value', min: 0, minInterval: 1, axisLabel: CHART_AXIS_LABEL },
    series: bands.map(band => ({
      ...band,
      type: 'bar' as const,
      stack: 'calls',
      barCategoryGap: '30%',
      // Pinned so hovering one band does not fade the others' fill.
      emphasis: { focus: 'none' as const }
    }))
  }
}
