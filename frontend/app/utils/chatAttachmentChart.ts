import type { EChartsOption } from 'echarts'
import type { ChatAttachment, ChatFrame } from '~/composables/useChatApi'

// Pure: a chart attachment (four-field spec + dataframe dict) → ECharts option.
// The model never sends an option; this is the only place one is built for
// chat, so colors, axes and tooltips follow the app theme like every page.
//
// `series_by` pivots long-form rows: one series per distinct value of that
// column, each plotting `y[0]` against `x`. Without it, each `y` column is a
// series. That is the whole vocabulary — a report needs "these counts over
// these days", not a grammar of graphics.

type Cell = ChatFrame['rows'][number][number]

const columnIndex = (frame: ChatFrame, name: string): number => frame.columns.indexOf(name)

const asNumber = (value: Cell): number | null => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  return null
}

const asLabel = (value: Cell): string => (value == null ? '' : String(value))

export interface AttachmentSeries {
  name: string
  points: (number | null)[]
}

/** Categories on x (in first-seen order) and one series per y column or group. */
export const pivotAttachment = (
  attachment: ChatAttachment
): { categories: string[], series: AttachmentSeries[] } => {
  const { data, chart } = attachment
  if (!chart) return { categories: [], series: [] }
  const xi = columnIndex(data, chart.x)
  const categories: string[] = []
  const seen = new Map<string, number>()
  for (const row of data.rows) {
    const label = asLabel(row[xi] ?? null)
    if (!seen.has(label)) {
      seen.set(label, categories.length)
      categories.push(label)
    }
  }

  if (chart.series_by) {
    const gi = columnIndex(data, chart.series_by)
    const yi = columnIndex(data, chart.y[0] ?? '')
    const groups = new Map<string, (number | null)[]>()
    for (const row of data.rows) {
      const group = asLabel(row[gi] ?? null)
      let points = groups.get(group)
      if (!points) {
        points = categories.map(() => null)
        groups.set(group, points)
      }
      points[seen.get(asLabel(row[xi] ?? null))!] = asNumber(row[yi] ?? null)
    }
    return {
      categories,
      series: [...groups].map(([name, points]) => ({ name, points }))
    }
  }

  return {
    categories,
    series: chart.y.map((name) => {
      const yi = columnIndex(data, name)
      const points = categories.map(() => null as number | null)
      for (const row of data.rows) {
        points[seen.get(asLabel(row[xi] ?? null))!] = asNumber(row[yi] ?? null)
      }
      return { name, points }
    })
  }
}

export const buildAttachmentOption = (
  attachment: ChatAttachment,
  colors: readonly string[]
): EChartsOption => {
  const { categories, series } = pivotAttachment(attachment)
  const type = attachment.chart?.type ?? 'line'
  return {
    color: [...colors],
    grid: { left: 8, right: 12, top: series.length > 1 ? 36 : 12, bottom: 4, containLabel: true },
    legend: series.length > 1 ? { top: 0, type: 'scroll' } : { show: false },
    tooltip: { trigger: type === 'scatter' ? 'item' : 'axis', confine: true },
    xAxis: {
      type: 'category',
      data: categories,
      axisTick: { show: false },
      axisLabel: { hideOverlap: true }
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: series.map(s => ({
      name: s.name,
      type,
      data: s.points,
      // A day with no row is a gap, not a zero.
      connectNulls: false,
      showSymbol: s.points.length <= 40,
      symbolSize: type === 'scatter' ? 7 : 5,
      smooth: false,
      barMaxWidth: 28
    }))
  }
}
