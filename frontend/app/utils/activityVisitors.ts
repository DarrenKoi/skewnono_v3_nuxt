import type { EChartsOption } from 'echarts'
import { CHART_AXIS_LABEL } from './chartType.ts'
import type { DailyVisitors } from '~/composables/useActivityApi'

/**
 * The admin 일별 방문자 chart's windows and ECharts option, built without
 * importing echarts — same reason as activitySparkline.ts: `npm test` runs
 * this under `node --test`.
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

// The weekday is named because it is the first thing the shape raises: a dip
// every seven bars is a weekend, not a problem.
export const visitorTooltip = (iso: string, visitors: number): string => {
  const weekday = DAY_NAMES[new Date(`${iso}T00:00:00Z`).getUTCDay()]
  return `${iso}${weekday ? ` (${weekday})` : ''} · 방문자 ${visitors.toLocaleString()}명`
}

export const buildVisitorsOption = (series: readonly DailyVisitors[]): EChartsOption => ({
  grid: { left: 44, right: 12, top: 16, bottom: 28 },
  tooltip: {
    // 'axis' so the whole column is the hit target — a one-visitor day is a
    // sliver of a bar next to a busy one.
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      if (!first) return ''
      const { axisValue, data } = first as { axisValue?: unknown, data?: unknown }
      return visitorTooltip(String(axisValue ?? ''), Number(data ?? 0))
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
  series: [{
    type: 'bar',
    data: series.map(day => day.visitors),
    barCategoryGap: '30%',
    itemStyle: { borderRadius: [2, 2, 0, 0] }
  }]
})
