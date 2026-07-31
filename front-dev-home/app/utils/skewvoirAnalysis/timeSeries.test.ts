import { test } from 'node:test'
import assert from 'node:assert/strict'
import { setBaseline, buildTrendSeries, type TrendRowInput, type TrendFileInput } from './timeSeries.ts'
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
