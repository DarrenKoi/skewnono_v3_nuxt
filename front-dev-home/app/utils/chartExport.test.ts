// front-dev-home/app/utils/chartExport.test.ts
// Pure-logic tests for chart-image export filename building.
// Run: cd front-dev-home && node --test app/utils/chartExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { slugifyChartName, formatDateStamp, chartExportFilename } from './chartExport.ts'

const D = new Date(2026, 6, 6) // 2026-07-06 (month is 0-indexed)

test('slugifyChartName lowercases and hyphenates', () => {
  assert.equal(slugifyChartName('Top 20 recipes by total TAT'), 'top-20-recipes-by-total-tat')
})

test('slugifyChartName collapses runs and trims edges', () => {
  assert.equal(slugifyChartName('  Daily / TAT  Trend!! '), 'daily-tat-trend')
})

test('slugifyChartName falls back to "chart" when empty after cleaning', () => {
  assert.equal(slugifyChartName('!!!'), 'chart')
})

test('formatDateStamp zero-pads month and day', () => {
  assert.equal(formatDateStamp(D), '2026-07-06')
})

test('chartExportFilename prefers exportName over title', () => {
  assert.equal(chartExportFilename('daily-tat-trend', 'Some Title', D), 'daily-tat-trend-2026-07-06.png')
})

test('chartExportFilename falls back to title text when no exportName', () => {
  assert.equal(chartExportFilename(undefined, 'Top 20 recipes by total TAT', D), 'top-20-recipes-by-total-tat-2026-07-06.png')
})

test('chartExportFilename falls back to "chart" when neither is given', () => {
  assert.equal(chartExportFilename(undefined, undefined, D), 'chart-2026-07-06.png')
})

test('chartExportFilename ignores blank/whitespace inputs', () => {
  assert.equal(chartExportFilename('   ', '   ', D), 'chart-2026-07-06.png')
})
