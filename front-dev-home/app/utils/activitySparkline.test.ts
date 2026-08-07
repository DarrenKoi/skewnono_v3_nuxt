import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildSparklineOption,
  formatSparklineDay,
  formatSparklineTooltip,
  sparklineHasData,
  sparklineTotal
} from './activitySparkline.ts'

const SERIES = [
  { date: '2026-07-01', count: 3 },
  { date: '2026-07-02', count: 0 },
  { date: '2026-07-03', count: 7 }
]

test('formats a day as MM.DD and passes through an unparseable date', () => {
  assert.equal(formatSparklineDay('2026-07-01'), '07. 01.')
  assert.equal(formatSparklineDay('not-a-date'), 'not-a-date')
})

test('totals the counts and reports whether any activity exists', () => {
  assert.equal(sparklineTotal(SERIES), 10)
  assert.equal(sparklineHasData(SERIES), true)
  assert.equal(sparklineTotal([]), 0)
  assert.equal(sparklineHasData([]), false)
  assert.equal(sparklineHasData([{ date: '2026-07-01', count: 0 }]), false)
})

test('maps every day to one bar, in order', () => {
  const option = buildSparklineOption(SERIES, '#123456', false)
  const series = option.series as Array<{ data: number[], type: string }>
  assert.equal(series.length, 1)
  assert.equal(series[0]!.type, 'bar')
  assert.deepEqual(series[0]!.data, [3, 0, 7])

  const xAxis = option.xAxis as { data: string[] }
  assert.deepEqual(xAxis.data, ['2026-07-01', '2026-07-02', '2026-07-03'])
})

test('paints the bars with the colour it was handed', () => {
  const option = buildSparklineOption(SERIES, '#123456', false)
  const series = option.series as Array<{ itemStyle: { color: string } }>
  assert.equal(series[0]!.itemStyle.color, '#123456')
})

test('adds dataZoom only when zoomable', () => {
  assert.equal(buildSparklineOption(SERIES, '#123456', false).dataZoom, undefined)

  const zoomed = buildSparklineOption(SERIES, '#123456', true)
  const dataZoom = zoomed.dataZoom as Array<{ type: string }>
  assert.deepEqual(dataZoom.map(z => z.type), ['inside', 'slider'])
})

test('reserves bottom room for the slider only when zoomable', () => {
  const flat = buildSparklineOption(SERIES, '#123456', false).grid as { bottom: number }
  const zoomed = buildSparklineOption(SERIES, '#123456', true).grid as { bottom: number }
  assert.equal(flat.bottom, 2)
  assert.ok(zoomed.bottom > flat.bottom, 'the slider needs bottom padding')
})

test('survives an empty series', () => {
  const option = buildSparklineOption([], '#123456', false)
  const series = option.series as Array<{ data: number[] }>
  assert.deepEqual(series[0]!.data, [])
})

test('renders the tooltip as date and count', () => {
  assert.equal(formatSparklineTooltip('2026-07-03', 7), '07. 03. · 7건')
})
