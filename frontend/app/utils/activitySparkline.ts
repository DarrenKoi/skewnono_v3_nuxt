import type { EChartsOption } from 'echarts'
import type { CountedDay, DailyCount } from '~/composables/useActivityApi'

/**
 * The activity sparkline's ECharts option, built without importing echarts.
 *
 * echarts is a runtime dependency of the component, not of this module: the
 * option is a plain object literal, and `npm test` runs this file directly
 * under `node --test`, where pulling in echarts would drag a browser-only
 * dependency into the test process for no gain. Keeping it out is what makes
 * the bar mapping and the tooltip text testable as pure functions — the chart
 * itself is only verifiable in a browser.
 */

/** 'MM.DD' as ko-KR renders it ("07. 01."), or the raw string when it will not parse. */
export const formatSparklineDay = (iso: string): string => {
  const date = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })
}

export const sparklineTotal = (series: readonly CountedDay[]): number =>
  series.reduce((sum, d) => sum + d.count, 0)

/**
 * Whether the chart is worth drawing at all. A 30-day window of zeroes is a
 * real answer ("no activity"), and the component renders text for it rather
 * than an empty canvas — which also means no ECharts instance is created for
 * the inactive users in the user table, where a row expands one chart each.
 */
export const sparklineHasData = (series: readonly CountedDay[]): boolean =>
  series.some(d => d.count > 0)

export const formatSparklineTooltip = (iso: string, count: number): string =>
  `${formatSparklineDay(iso)} · ${count}건`

export const buildSparklineOption = (
  series: DailyCount[],
  barColor: string
): EChartsOption => ({
  // No axis furniture. The host is 64px tall and the total/dates live in HTML
  // around the canvas, so every pixel in here belongs to the bars.
  grid: {
    left: 0,
    right: 0,
    top: 2,
    bottom: 2,
    containLabel: false
  },
  xAxis: {
    type: 'category',
    data: series.map(d => d.date),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    splitLine: { show: false }
  },
  yAxis: {
    type: 'value',
    min: 0,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    splitLine: { show: false }
  },
  tooltip: {
    // 'axis' rather than 'item' so the whole column is a hit target: a
    // one-request day is a 2px-tall bar that an 'item' trigger makes
    // practically unhoverable.
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      if (!first) return ''
      const { axisValue, data } = first as { axisValue?: unknown, data?: unknown }
      return formatSparklineTooltip(String(axisValue ?? ''), Number(data ?? 0))
    }
  },
  series: [{
    type: 'bar',
    data: series.map(d => d.count),
    barCategoryGap: '20%',
    itemStyle: { color: barColor, borderRadius: [1.5, 1.5, 0, 0] }
  }]
})
