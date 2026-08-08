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
  const option = buildSparklineOption(SERIES, '#123456')
  const series = option.series as Array<{ data: number[], type: string }>
  assert.equal(series.length, 1)
  assert.equal(series[0]!.type, 'bar')
  assert.deepEqual(series[0]!.data, [3, 0, 7])

  const xAxis = option.xAxis as { data: string[] }
  assert.deepEqual(xAxis.data, ['2026-07-01', '2026-07-02', '2026-07-03'])
})

test('paints the bars with the colour it was handed', () => {
  const option = buildSparklineOption(SERIES, '#123456')
  const series = option.series as Array<{ itemStyle: { color: string } }>
  assert.equal(series[0]!.itemStyle.color, '#123456')
})

test('draws no zoom control', () => {
  // The slider was tried and pulled: it ate a third of a 64px host and read as
  // furniture rather than a control. Asserted rather than merely absent so a
  // future "just add dataZoom" has to argue with a test first.
  assert.equal(buildSparklineOption(SERIES, '#123456').dataZoom, undefined)
})

test('leaves the plot area unpadded — nothing sits below the bars', () => {
  const grid = buildSparklineOption(SERIES, '#123456').grid as { bottom: number }
  assert.equal(grid.bottom, 2)
})

test('survives an empty series', () => {
  const option = buildSparklineOption([], '#123456')
  const series = option.series as Array<{ data: number[] }>
  assert.deepEqual(series[0]!.data, [])
})

test('renders the tooltip as date and count', () => {
  assert.equal(formatSparklineTooltip('2026-07-03', 7), '07. 03. · 7건')
})
