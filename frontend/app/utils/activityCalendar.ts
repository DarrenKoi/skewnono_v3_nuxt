import type { EChartsOption } from 'echarts'
import type { VisitCount } from '~/composables/useActivityApi'

/**
 * The visit calendar's ECharts option, built without importing echarts — same
 * reason as activitySparkline.ts: `npm test` runs this under `node --test`.
 */

export type VisitDay = VisitCount

export const visitLabel = (day: VisitDay) => `${day.date} · 페이지 조회 ${day.count.toLocaleString()}회`

const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토']

export const buildCalendarOption = (
  series: readonly VisitDay[],
  colors: { empty: string, full: string, ink: string, muted: string }
): EChartsOption => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      const value = (first as { value?: unknown } | undefined)?.value
      if (!Array.isArray(value)) return ''
      return visitLabel({ date: String(value[0]), count: Number(value[1]) })
    }
  },
  visualMap: {
    show: false,
    min: 0,
    max: Math.max(1, ...series.map(day => day.count)),
    inRange: { color: [colors.empty, colors.full] }
  },
  calendar: {
    left: 28,
    right: 4,
    top: 24,
    bottom: 4,
    cellSize: ['auto', 18],
    orient: 'horizontal',
    range: series.length ? [series[0]!.date, series[series.length - 1]!.date] : undefined,
    splitLine: { show: false },
    itemStyle: { borderWidth: 2, borderColor: 'transparent' },
    dayLabel: { firstDay: 1, nameMap: DAY_NAMES, color: colors.muted, fontSize: 11, margin: 6 },
    monthLabel: { formatter: '{M}월', color: colors.muted, fontSize: 11, margin: 6 },
    yearLabel: { show: false }
  },
  series: [{
    type: 'heatmap',
    coordinateSystem: 'calendar',
    data: series.map(day => [day.date, day.count]),
    itemStyle: { borderRadius: 3 },
    emphasis: { itemStyle: { borderColor: colors.ink, borderWidth: 1 } }
  }]
})
