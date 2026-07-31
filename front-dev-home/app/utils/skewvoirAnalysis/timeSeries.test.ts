import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  setBaseline, buildTrendSeries, buildSetDistributionGroups, buildToolSkew, distinctToolCount,
  type TrendRowInput, type TrendFileInput, type TrendPoint, type DistFileInput
} from './timeSeries.ts'
import { DEFAULT_METHOD_CONFIG } from '../anomaly/types.ts'

const row = (msr: string, eqpId: string, timestamp: string): TrendRowInput =>
  ({ msr, label: `${eqpId} · ${timestamp}`, eqpId, timestamp })

const file = (parameter: string, mean: number, min: number, max: number, std: number): TrendFileInput =>
  ({ parameters: [{ parameter, count: 9, mean, std, min, max, unit: 'nm' }] })

test('setBaseline returns the median and does NOT require pre-sorted input', () => {
  // quantileSorted indexes without sorting — an unsorted caller silently gets
  // a wrong "median", so setBaseline must sort defensively.
  assert.equal(setBaseline([5, 1, 3]), 3)
  assert.equal(setBaseline([10, 2, 8, 4]), 6) // even count → midpoint of 4 and 8
  assert.equal(setBaseline([7]), 7)
  assert.ok(Number.isNaN(setBaseline([])))
})

test('buildTrendSeries sorts by timestamp, not by authored order', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-03T10:00:00'),
    row('m2', 'TP02', '2026-07-01T10:00:00'),
    row('m3', 'TP03', '2026-07-02T10:00:00')
  ]
  const files = new Map<string, TrendFileInput>([
    ['m1', file('WAFER', 30, 28, 32, 1)],
    ['m2', file('WAFER', 10, 9, 11, 1)],
    ['m3', file('WAFER', 20, 19, 21, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m2', 'm3', 'm1'])
})

test('raw baseline leaves value and band equal to the measured statistics', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00')]
  const files = new Map([['m1', file('WAFER', 20, 18, 24, 2)]])
  const [p] = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.equal(p!.mean, 20)
  assert.equal(p!.value, 20)
  assert.equal(p!.bandLo, 18)
  assert.equal(p!.bandHi, 24)
})

test('residual baseline shifts value AND both band edges by the same amount', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-01T10:00:00'),
    row('m2', 'TP02', '2026-07-02T10:00:00'),
    row('m3', 'TP03', '2026-07-03T10:00:00')
  ]
  const files = new Map([
    ['m1', file('WAFER', 10, 8, 12, 1)],
    ['m2', file('WAFER', 20, 18, 24, 2)],
    ['m3', file('WAFER', 30, 28, 32, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'resid', config: DEFAULT_METHOD_CONFIG })
  const mid = out.find(p => p.msr === 'm2')!
  assert.equal(mid.mean, 20) // raw statistic preserved
  assert.equal(mid.value, 0) // 20 - median(10,20,30) = 0
  assert.equal(mid.bandLo, -2) // 18 - 20
  assert.equal(mid.bandHi, 4) // 24 - 20
  assert.equal(mid.min, 18) // raw statistic preserved, NOT shifted
  assert.equal(mid.max, 24) // raw statistic preserved, NOT shifted
  assert.equal(mid.std, 2) // raw statistic preserved, NOT shifted
})

test('measurements whose file lacks the parameter are dropped', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-01T10:00:00'),
    row('m2', 'TP02', '2026-07-02T10:00:00')
  ]
  const files = new Map([
    ['m1', file('WAFER', 10, 9, 11, 1)],
    ['m2', file('GATE_CD', 50, 48, 52, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m1'])
})

test('an unparseable timestamp yields ts null and sorts to the end, still plotted', () => {
  const rows = [
    row('bad', 'TP09', 'not-a-date'),
    row('m1', 'TP01', '2026-07-01T10:00:00')
  ]
  const files = new Map([
    ['bad', file('WAFER', 15, 14, 16, 1)],
    ['m1', file('WAFER', 10, 9, 11, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m1', 'bad'])
  assert.equal(out[1]!.ts, null)
})

test('an unnamed settling MP gets no verdicts — no peer judgement on a warm-up shot', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('', 10 + i, 9 + i, 11 + i, 1)]))
  const out = buildTrendSeries(rows, files, '', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.equal(out.length, 6)
  assert.ok(out.every(p => p.verdict === undefined))
})

test('a named parameter DOES get verdicts once there are enough peers', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('WAFER', 10 + i, 9 + i, 11 + i, 1)]))
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.ok(out.every(p => p.verdict?.status === 'evaluated'))
})

test('verdicts are computed from RAW means, so residual mode cannot change them', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('WAFER', 100 + i, 99 + i, 101 + i, 1)]))
  const raw = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  const resid = buildTrendSeries(rows, files, 'WAFER', { baseline: 'resid', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(
    raw.map(p => p.verdict?.severity),
    resid.map(p => p.verdict?.severity)
  )
})

const siteRow = (parameter: string, mp_number: number, cd_value: number | null) =>
  ({ parameter, mp_number, cd_value })

test('buildSetDistributionGroups makes one group per measurement, measured sites only', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00'), row('m2', 'TP02', '2026-07-02T10:00:00')]
  const files = new Map<string, DistFileInput>([
    ['m1', { rows: [siteRow('WAFER', 0, 10), siteRow('WAFER', 1, 12), siteRow('GATE_CD', 2, 99)] }],
    ['m2', { rows: [siteRow('WAFER', 0, 20), siteRow('WAFER', -1, null)] }]
  ])
  const out = buildSetDistributionGroups(rows, files, 'WAFER')
  assert.deepEqual(out.map(g => g.label), ['TP01 · 2026-07-01T10:00:00', 'TP02 · 2026-07-02T10:00:00'])
  assert.deepEqual(out[0]!.values, [10, 12])
  assert.deepEqual(out[1]!.values, [20]) // the mp_number -1 / null site is excluded
})

test('buildSetDistributionGroups drops a measurement with no measured site', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00'), row('m2', 'TP02', '2026-07-02T10:00:00')]
  const files = new Map<string, DistFileInput>([
    ['m1', { rows: [siteRow('WAFER', 0, 10)] }],
    ['m2', { rows: [siteRow('WAFER', -1, null)] }]
  ])
  const out = buildSetDistributionGroups(rows, files, 'WAFER')
  assert.deepEqual(out.map(g => g.label), ['TP01 · 2026-07-01T10:00:00'])
})

test('buildToolSkew groups by equipment, offsets against the set baseline', () => {
  const points = [
    { eqpId: 'TP01', mean: 10 }, { eqpId: 'TP01', mean: 12 },
    { eqpId: 'TP02', mean: 30 }
  ] as TrendPoint[]
  const out = buildToolSkew(points, 20)
  const tp01 = out.find(r => r.eqpId === 'TP01')!
  assert.equal(tp01.n, 2)
  assert.equal(tp01.mean, 11)
  assert.equal(tp01.offset, -9)
  assert.equal(tp01.sigma, Math.sqrt(2)) // sample std of [10, 12]
})

test('buildToolSkew reports sigma null for a single-measurement tool', () => {
  // sampleStd returns 0 for n<2; rendering that reads as "no variation" when
  // the truth is "not estimable".
  const points = [{ eqpId: 'TP01', mean: 10 }, { eqpId: 'TP02', mean: 30 }] as TrendPoint[]
  const out = buildToolSkew(points, 20)
  assert.ok(out.every(r => r.n === 1))
  assert.ok(out.every(r => r.sigma === null))
})

test('buildToolSkew sorts by absolute offset, most-skewed tool first', () => {
  const points = [
    { eqpId: 'NEAR', mean: 21 }, { eqpId: 'FAR', mean: 40 }, { eqpId: 'MID', mean: 14 }
  ] as TrendPoint[]
  assert.deepEqual(buildToolSkew(points, 20).map(r => r.eqpId), ['FAR', 'MID', 'NEAR'])
})

test('buildToolSkew produces NO rows for a single-tool set', () => {
  // An offset against a baseline the tool itself defines is not a comparison.
  // The spec requires no row at all — the panel says 단일 장비 instead.
  const points = [{ eqpId: 'TP01', mean: 10 }, { eqpId: 'TP01', mean: 20 }] as TrendPoint[]
  assert.deepEqual(buildToolSkew(points, 15), [])
})

test('buildToolSkew on an empty set returns no rows', () => {
  assert.deepEqual(buildToolSkew([], Number.NaN), [])
})

test('distinctToolCount lets the panel tell "one tool" apart from "no data"', () => {
  // Both cases give buildToolSkew an empty array, but they need different copy.
  assert.equal(distinctToolCount([{ eqpId: 'TP01', mean: 10 }] as TrendPoint[]), 1)
  assert.equal(distinctToolCount([]), 0)
  assert.equal(distinctToolCount([
    { eqpId: 'TP01', mean: 10 }, { eqpId: 'TP02', mean: 20 }
  ] as TrendPoint[]), 2)
})
