// Pure-logic tests for afmTrend. Run: node --test app/utils/afmTrend.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailPayload, AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import {
  controlLimits,
  healthSeries,
  isOutside,
  measurementStats,
  missingReason,
  pointMatrix,
  pointStability,
  prepareEntries,
  quartiles,
  repeatPairs,
  robustSd,
  tipChanges,
  trendRows,
  trendTable,
  varianceSplit,
  type TrendSource
} from './afmTrend.ts'

const COL = 'Left_H (nm)'

const row = (point: string, value: number | string | null, extra: Partial<AfmDetailRow> = {}): AfmDetailRow => ({
  'measurement_point': point,
  'Point No': Number(point),
  'X (um)': 0,
  'Y (um)': 0,
  'Method_ID': 2,
  'State': 'COMPLETED',
  'Valid': true,
  'Pick Up Count': 1,
  'Sample Count': 1,
  'Approach Count': 1,
  'Mileage': 10,
  ...(value === null ? {} : { [COL]: value }),
  ...extra
} as AfmDetailRow)

const summaryOf = (site: string, stats: Record<string, number | string>): AfmSummaryRow[] =>
  Object.entries(stats).map(([ITEM, value]) => ({ Site: site, ITEM, [COL]: value }))

const payload = (summary: AfmSummaryRow[], data: AfmDetailRow[], information: Record<string, string> = {}): AfmDetailPayload => ({
  filename: 'f', tool: 'MAP608', pickle_filename: 'f.pkl', information, summary, data, available_points: []
})

const source = (filename: string, extra: Partial<TrendSource> = {}): TrendSource => ({
  filename, recipeName: 'VED_BS_TOP01', lotId: 'LOT1', slotNumber: 3, formattedDate: '2026-10-01', ...extra
})

test('robustSd ignores one excursion, and falls back to STDEV when the MAD is 0', () => {
  const calm = [10, 10.2, 9.8, 10.1, 9.9]
  assert.ok(Math.abs(robustSd([...calm, 30]) - robustSd(calm)) < 0.1)
  // Half the values identical → MAD 0 → sample STDEV.
  assert.equal(robustSd([1, 1, 1, 5]), 2)
})

test('controlLimits are μ ± 3σ, and need two values', () => {
  assert.equal(controlLimits([]), null)
  assert.equal(controlLimits([5]), null)
  const limits = controlLimits([9, 10, 11])!
  assert.equal(limits.mu, 10)
  assert.equal(limits.sigma, 1.4826)
  assert.ok(Math.abs(limits.ucl - (10 + 3 * 1.4826)) < 1e-9)
  assert.ok(isOutside(20, limits))
  assert.ok(!isOutside(10, limits))
  assert.ok(!isOutside(1e9, null))
})

test('quartiles are R-7 and null on nothing', () => {
  assert.deepEqual(quartiles([1, 2, 3, 4, 5]), { min: 1, q1: 2, median: 3, q3: 4, max: 5 })
  assert.equal(quartiles([]), null)
})

test('measurementStats prefers the Summary and counts rows from data', () => {
  const [entry] = prepareEntries([{
    source: source('a'),
    payload: payload(
      summaryOf('Profile_LEFT_UL', { MEAN: '80.5', STDEV: 1, MIN: 79, MAX: 82, RANGE: 3 }),
      [row('1', 79), row('2', 82, { Valid: false }), row('3', 'n/a', { State: 'FAILED' })]
    )
  }])
  const stats = measurementStats(entry!, 'Profile_LEFT_UL', COL)!
  assert.equal(stats.source, 'summary')
  assert.equal(stats.MEAN, 80.5)
  assert.equal(stats.n, 3)
  assert.equal(stats.nValid, 1)
  // A non-numeric cell is no value at all, never 0.
  assert.deepEqual([...stats.points.entries()], [['1', 79], ['2', 82]])
  assert.equal(stats.box?.median, 80.5)
})

test('measurementStats computes from data when the Summary is empty', () => {
  const [entry] = prepareEntries([{ source: source('a'), payload: payload([], [row('1', 1), row('2', 3)]) }])
  const stats = measurementStats(entry!, 'Block 1', COL)!
  assert.equal(stats.source, 'data')
  assert.deepEqual([stats.MEAN, stats.MIN, stats.MAX, stats.RANGE], [2, 1, 3, 2])
  assert.ok(Math.abs(stats.STDEV! - Math.SQRT2) < 1e-12)
})

test('measurementStats keeps Summary-only stats when there is no data table', () => {
  const [entry] = prepareEntries([{ source: source('a'), payload: payload(summaryOf('B', { MEAN: 5 }), []) }])
  const stats = measurementStats(entry!, 'B', COL)!
  assert.equal(stats.MEAN, 5)
  assert.equal(stats.STDEV, null)
  assert.equal(stats.n, null)
  assert.equal(stats.box, null)
  assert.equal(stats.points.size, 0)
})

test('measurementStats is null for a missing block or column, and says why', () => {
  const stopped = [row('1', 1, { Site: 'L' }), row('2', 2, { Site: 'L' }), row('1', null, { State: 'STOPPED', Site: 'R' })]
  const [entry] = prepareEntries([{ source: source('a'), payload: payload(summaryOf('L', { MEAN: 1.5 }), stopped) }])
  assert.equal(measurementStats(entry!, 'L', 'Other (nm)'), null)
  // The stopped second block has the row it stopped on, no Summary, no values.
  assert.deepEqual(entry!.blocks, ['L', 'R'])
  assert.equal(measurementStats(entry!, 'R', COL), null)
  assert.equal(missingReason(entry!, 'R'), '블록 STOPPED')
  assert.equal(missingReason(entry!, 'Nope'), '블록 없음')
})

test('a Summary-less file lines up with its siblings by the rows\' own block', () => {
  const twoBlocks = [row('1', 1, { Site: 'L' }), row('2', 2, { Site: 'L' }), row('1', 7, { Site: 'R' }), row('2', 9, { Site: 'R' })]
  // A repeat recipe: the points come round again inside one block.
  const repeat = [row('1', 1, { Site: 'L' }), row('2', 3, { Site: 'L' }), row('1', 5, { Site: 'L' }), row('2', 7, { Site: 'L' })]
  const entries = prepareEntries([
    { source: source('named'), payload: payload([...summaryOf('L', { MEAN: 1 }), ...summaryOf('R', { MEAN: 8 })], twoBlocks) },
    { source: source('bare'), payload: payload([], twoBlocks) },
    { source: source('repeat'), payload: payload([], repeat) },
    { source: source('unnamed'), payload: payload([], [row('1', 1), row('1', 3)]) }
  ])
  const bare = entries.find(e => e.key === 'bare')!
  assert.deepEqual(bare.blocks, ['L', 'R'])
  assert.equal(measurementStats(bare, 'R', COL)!.MEAN, 8)
  const repeated = entries.find(e => e.key === 'repeat')!
  assert.deepEqual(repeated.blocks, ['L'])
  assert.equal(measurementStats(repeated, 'L', COL)!.n, 4)
  assert.deepEqual(entries.find(e => e.key === 'unnamed')!.blocks, ['Block 1'])
})

test('prepareEntries sorts by Start Time and reads Sample ID, else lot.slot', () => {
  const entries = prepareEntries([
    { source: source('late'), payload: payload([], [], { 'Start Time': '2026-10-02 10:00:00', 'Sample ID': 'S.01' }) },
    { source: source('early', { formattedDate: '2026-09-30' }), payload: payload([], [], { 'Start Time': '' }) }
  ])
  assert.deepEqual(entries.map(e => e.key), ['early', 'late'])
  assert.deepEqual(entries.map(e => e.sample), ['LOT1.3', 'S.01'])
})

test('pointMatrix unions points in natural order and picks the baseline', () => {
  const series = [
    { key: 'a', points: new Map([['2', 2], ['10', 10]]) },
    { key: 'b', points: new Map([['2', 4]]) }
  ]
  const byMean = pointMatrix(series, 'mean', null)
  assert.deepEqual(byMean.points, ['2', '10'])
  assert.deepEqual(byMean.rows[1]!.values, [4, null])
  assert.deepEqual(byMean.baseline, [3, 10])
  assert.deepEqual(pointMatrix(series, 'first', null).baseline, [2, 10])
  assert.deepEqual(pointMatrix(series, 'selected', 'b').baseline, [4, null])
  const lost = pointMatrix(series, 'selected', 'gone')
  assert.equal(lost.baselineUsed, 'mean')
  assert.deepEqual(lost.baseline, [3, 10])
})

test('pointStability flags the point whose STDEV clears mean + 1.5·sd', () => {
  const points = (wobble: number) => new Map(Array.from({ length: 10 }, (_, i) => [String(i + 1), i === 6 ? 50 + wobble : 50 + wobble / 20]))
  const matrix = pointMatrix([points(0), points(8), points(-6), points(3)].map((p, i) => ({ key: String(i), points: p })), 'mean', null)
  const stability = pointStability(matrix)
  assert.deepEqual(stability.filter(s => s.unstable).map(s => s.point), ['7'])
  const lone = pointStability(pointMatrix([{ key: 'a', points: new Map([['1', 1]]) }], 'mean', null))
  assert.deepEqual(lone, [{ point: '1', sd: null, unstable: false }])
})

test('varianceSplit is lot σ of the MEANs against the mean wafer σ', () => {
  const split = varianceSplit([{ MEAN: 1, STDEV: 1 }, { MEAN: 3, STDEV: 1 }, { MEAN: null, STDEV: 5 }])!
  assert.ok(Math.abs(split.lotSd - Math.SQRT2) < 1e-12)
  assert.equal(split.waferSd, 7 / 3)
  assert.equal(split.lotPct, Math.round(100 * 2 / (2 + (7 / 3) ** 2)))
  assert.equal(varianceSplit([{ MEAN: 1, STDEV: 1 }]), null)
})

test('repeatPairs groups one sample under one recipe and rates the spread', () => {
  const pairs = repeatPairs([
    { key: 'a', sample: 'S.1', recipe: 'R', time: 0, mean: 10 },
    { key: 'b', sample: 'S.2', recipe: 'R', time: 1, mean: 11 },
    { key: 'c', sample: 'S.1', recipe: 'R', time: 7_200_000, mean: 10.5 },
    { key: 'd', sample: 'S.1', recipe: 'Q', time: 9e6, mean: 99 },
    { key: 'e', sample: 'S.1', recipe: 'Q', time: 9e6, mean: null }
  ], recipe => recipe === 'R' ? 1 : null)
  assert.equal(pairs.length, 1)
  assert.deepEqual(pairs[0], { sample: 'S.1', recipe: 'R', keys: ['a', 'c'], hours: 2, spread: 0.5, ratio: 0.5 })
  // Q's S.1 has one MEAN between two files: nothing to compare.
  assert.equal(repeatPairs([{ key: 'a', sample: 'S', recipe: 'R', time: 0, mean: 1 }, { key: 'b', sample: 'S', recipe: 'R', time: 0, mean: 3 }], () => null)[0]!.ratio, null)
})

test('healthSeries counts every block\'s rows; only a stated FALSE is invalid', () => {
  const [entry] = prepareEntries([{
    source: source('a'),
    payload: payload([], [
      row('1', 1, { 'Approach Count': 1, 'Mileage': 4 }),
      row('2', 1, { 'State': 'FAILED', 'Approach Count': 3, 'Mileage': 'x' as unknown as number }),
      row('1', 1, { Valid: false }),
      row('2', 1, { Valid: '' as unknown as boolean })
    ])
  }])
  assert.deepEqual(healthSeries([entry!])[0], { key: 'a', time: entry!.time, notCompleted: 1, invalid: 1, approach: 1.5, mileage: 8, tip: null, tipWidth: null })
  const [empty] = prepareEntries([{ source: source('b'), payload: payload([], []) }])
  assert.equal(healthSeries([empty!])[0]!.approach, null)
})

test('healthSeries reads the tip from Info; tipChanges marks where ID or seat differs', () => {
  const at = (name: string, minute: number, info: Record<string, string | null>) => {
    const p = payload([], [row('1', 1)])
    return { source: source(name), payload: { ...p, information: { ...p.information, 'Start Time': `2026-10-06 06:${String(minute).padStart(2, '0')}:00`, ...info } } }
  }
  const seat = { 'Tip Cassette ID': 'TC1', 'Tip Port No': '1', 'Tip Slot No': '3' }
  const health = healthSeries(prepareEntries([
    at('a', 0, { ...seat, 'Tip ID': 'T1', 'Tip Width': '40.9' }),
    at('b', 1, { 'Tip ID': null, 'Tip Width': null }),
    at('c', 2, { ...seat, 'Tip ID': 'T1', 'Tip Width': '41.2 nm' }),
    // Same Tip ID in another slot is another tip; its width is the office's 'NaN'.
    at('d', 3, { ...seat, 'Tip ID': 'T1', 'Tip Slot No': '7', 'Tip Width': 'NaN' }),
    at('e', 4, { ...seat, 'Tip ID': 'T2', 'Tip Slot No': '7', 'Tip Width': '39' })
  ]))
  const by = new Map(health.map(h => [h.key, h]))
  assert.deepEqual([by.get('a')!.tip, by.get('a')!.tipWidth], ['T1 · TC1/1/3', 40.9])
  assert.deepEqual([by.get('b')!.tip, by.get('b')!.tipWidth], [null, null])
  assert.equal(by.get('c')!.tipWidth, 41.2)
  assert.deepEqual([by.get('d')!.tip, by.get('d')!.tipWidth], ['T1 · TC1/1/7', null])
  // The unnamed measurement between two identical tips is not a change.
  assert.deepEqual(tipChanges(health), [by.get('d')!.time, by.get('e')!.time])
  // Mileage belongs to the tip: where it falls, the tip is a new one even if
  // every Tip value reads the same.
  const worn = health.map((h, i) => ({ ...h, tip: 'T1 · TC1/1/3', mileage: [900, 950, 1000, 12, 40][i]! }))
  assert.deepEqual(tipChanges(worn), [worn[3]!.time])
})

test('trendRows keeps μ, limits and Δ inside each recipe, and lists what is missing', () => {
  const entry = (name: string, recipe: string, mean: number) =>
    ({ source: source(name, { recipeName: recipe }), payload: payload(summaryOf('B', { MEAN: mean }), [row('1', mean)]) })
  const entries = prepareEntries([
    // μ is the plain mean, σ the MAD one: the excursion drags μ by 0.3, not σ.
    ...[10, 10.4, 9.6, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7].map((v, i) => entry(i ? `r${i}` : 'a', 'R', v)),
    entry('d', 'R', 13),
    entry('e', 'Q', 100),
    { source: source('f', { recipeName: 'R' }), payload: payload(summaryOf('Other', { MEAN: 1 }), []) }
  ])
  const { rows, centres } = trendRows(entries, 'B', COL, 'MEAN', true)
  const byKey = new Map(rows.map(r => [r.entry.key, r]))
  assert.equal(byKey.get('d')!.out, true)
  assert.equal(byKey.get('a')!.out, false)
  assert.ok(Math.abs(centres.get('R')!.mu! - 10.3) < 1e-9)
  assert.ok(Math.abs(byKey.get('a')!.delta! + 0.3) < 1e-9)
  assert.equal(rows.filter(r => r.out).length, 1)
  // Alone in its recipe: a centre, so Δ 0, but no limits to fall outside of.
  assert.equal(centres.get('Q')!.limits, null)
  assert.deepEqual([byKey.get('e')!.delta, byKey.get('e')!.out], [0, false])
  assert.deepEqual([byKey.get('f')!.value, byKey.get('f')!.reason, byKey.get('f')!.state], [null, '블록 없음', null])
  assert.equal(byKey.get('a')!.state, 'COMPLETED')
  assert.ok(!trendRows(entries, 'B', COL, 'MEAN', false).rows.some(r => r.out))
})

test('trendTable writes one numeric cell per column and names the reason for a gap', () => {
  const [entry] = prepareEntries([{ source: source('a.csv'), payload: payload(summaryOf('B', { MEAN: 2 }), []) }])
  const table = trendTable(trendRows([entry!], 'B', COL, 'MEAN', true).rows)
  assert.equal(table.headers.length, table.rows[0]!.length)
  assert.deepEqual(table.rows[0]!.slice(1), ['VED_BS_TOP01', 'LOT1', '3', null, null, 2, null, null, null, null, 0, null, 'a.csv'])
  const missing = trendTable(trendRows([entry!], 'Z', COL, 'MEAN', true).rows)
  assert.equal(missing.rows[0]![12], '블록 없음')
})

// The chart tick can drop the year; a sheet cannot — it outlives the screen,
// and a group can straddle New Year.
test('trendTable writes the full start time, year included', () => {
  const [entry] = prepareEntries([{
    source: source('a.csv'),
    payload: payload(summaryOf('B', { MEAN: 2 }), [], { 'Start Time': '2025-12-31 23:45:00' })
  }])
  assert.equal(trendTable(trendRows([entry!], 'B', COL, 'MEAN', true).rows).rows[0]![0], '2025-12-31 23:45')
})
