import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { buildAttachmentOption, pivotAttachment } from './chatAttachmentChart.ts'
import type { ChatAttachment } from '../composables/useChatApi.ts'

const wide: ChatAttachment = {
  kind: 'chart',
  title: 't',
  tool_name: 'fail_issue_daily_trend',
  data: {
    columns: ['date', 'exec_count', 'align_fail_count'],
    rows: [['09-12', 131, 9], ['09-13', 128, '12'], ['09-14', 140, null]],
    row_count: 3,
    truncated: false
  },
  chart: { type: 'line', x: 'date', y: ['align_fail_count', 'exec_count'], series_by: null }
}

const long: ChatAttachment = {
  ...wide,
  data: {
    columns: ['date', 'eqp_id', 'n'],
    rows: [['09-12', 'A', 1], ['09-12', 'B', 2], ['09-13', 'B', 4]],
    row_count: 3,
    truncated: false
  },
  chart: { type: 'bar', x: 'date', y: ['n'], series_by: 'eqp_id' }
}

describe('pivotAttachment', () => {
  it('makes one series per y column, coercing numeric strings and keeping gaps', () => {
    const { categories, series } = pivotAttachment(wide)
    assert.deepEqual(categories, ['09-12', '09-13', '09-14'])
    assert.deepEqual(series.map(s => s.name), ['align_fail_count', 'exec_count'])
    assert.deepEqual(series[0]!.points, [9, 12, null])
  })

  it('pivots long rows into one series per series_by value', () => {
    const { categories, series } = pivotAttachment(long)
    assert.deepEqual(categories, ['09-12', '09-13'])
    assert.deepEqual(series, [
      { name: 'A', points: [1, null] },
      { name: 'B', points: [2, 4] }
    ])
  })

  it('returns nothing for a table attachment', () => {
    assert.deepEqual(pivotAttachment({ ...wide, kind: 'table', chart: null }), { categories: [], series: [] })
  })
})

describe('buildAttachmentOption', () => {
  it('shows a legend only with several series and uses the chart type', () => {
    const one = buildAttachmentOption({ ...wide, chart: { ...wide.chart!, y: ['exec_count'] } }, ['#000'])
    assert.deepEqual(one.legend, { show: false })
    const many = buildAttachmentOption(long, ['#000', '#111'])
    assert.equal((many.legend as { top?: number }).top, 0)
    assert.equal((many.series as { type: string }[])[0]!.type, 'bar')
  })
})
