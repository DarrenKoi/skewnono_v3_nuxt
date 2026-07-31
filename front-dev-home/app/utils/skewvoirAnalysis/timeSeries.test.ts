import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  setBaseline, buildTrendSeries, placeTrendPoints,
  buildSetDistributionGroups, buildToolSkew, distinctToolCount,
  setParamOptions, setIntegrity,
  type TrendRowInput, type TrendFileInput, type TrendPoint, type DistFileInput, type OptionFileInput
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

const placeable = [
  { msr: 'm1', ts: 1000, eqpId: 'TP01' },
  { msr: 'm2', ts: null, eqpId: 'TP01' },
  { msr: 'm3', ts: 3000, eqpId: 'TP02' }
] as TrendPoint[]

test('placeTrendPoints drops the unplaceable points on a time axis and keeps epoch x', () => {
  // A null ts has no position on a time axis: plotting it anywhere would be an
  // invented timestamp, so it is hidden and the caller reports the count.
  const out = placeTrendPoints(placeable, 'time')
  assert.deepEqual(out.map(e => e.p.msr), ['m1', 'm3'])
  assert.deepEqual(out.map(e => e.x), [1000, 3000])
  assert.equal(placeable.length - out.length, 1) // what a panel meta reports
})

test('placeTrendPoints hides nothing on an order axis and indexes the FULL array', () => {
  // x must be the index into the full point list, because the category axis
  // data is built from every point — indexing the filtered array would slide
  // every label one slot left of its measurement.
  const out = placeTrendPoints(placeable, 'order')
  assert.deepEqual(out.map(e => e.p.msr), ['m1', 'm2', 'm3'])
  assert.deepEqual(out.map(e => e.x), [0, 1, 2])
})

test('placeTrendPoints keeps a ts of 0 rather than treating it as missing', () => {
  // Epoch 0 is falsy but perfectly placeable; only null means "no position".
  const out = placeTrendPoints([{ msr: 'm0', ts: 0 }] as TrendPoint[], 'time')
  assert.deepEqual(out.map(e => e.x), [0])
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

const optFile = (params: string[], mpRows: { parameter: string, mp_number: number, sequence: number }[]): OptionFileInput =>
  ({ parameters: params.map(p => ({ parameter: p, count: 1, mean: 0, std: 0, min: 0, max: 0, unit: 'nm' })), rows: mpRows })

test('setParamOptions counts how many LOADED measurements carry each parameter', () => {
  const rows = [row('m1', 'TP01', 't1'), row('m2', 'TP02', 't2'), row('m3', 'TP03', 't3')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['WAFER', 'GATE_CD'], [{ parameter: 'WAFER', mp_number: 1, sequence: 1 }, { parameter: 'GATE_CD', mp_number: 2, sequence: 2 }])],
    ['m2', optFile(['WAFER'], [{ parameter: 'WAFER', mp_number: 1, sequence: 1 }])]
    // m3 has no file — it was never loaded, so it is not in the denominator
  ])
  const out = setParamOptions(rows, files)
  assert.equal(out.find(o => o.parameter === 'WAFER')!.covered, 2)
  assert.equal(out.find(o => o.parameter === 'GATE_CD')!.covered, 1)
  assert.ok(out.every(o => o.loaded === 2))
})

test('setParamOptions sorts by coverage, then MP order, then name', () => {
  const rows = [row('m1', 'TP01', 't1'), row('m2', 'TP02', 't2')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['B_LATE', 'A_EARLY', 'RARE'], [
      { parameter: 'A_EARLY', mp_number: 1, sequence: 1 },
      { parameter: 'B_LATE', mp_number: 5, sequence: 5 },
      { parameter: 'RARE', mp_number: 9, sequence: 9 }
    ])],
    ['m2', optFile(['B_LATE', 'A_EARLY'], [
      { parameter: 'A_EARLY', mp_number: 1, sequence: 1 },
      { parameter: 'B_LATE', mp_number: 5, sequence: 5 }
    ])]
  ])
  // A_EARLY and B_LATE both cover 2; A_EARLY has the lower mp_number.
  // RARE covers 1, so it sorts last regardless of anything else.
  assert.deepEqual(setParamOptions(rows, files).map(o => o.parameter), ['A_EARLY', 'B_LATE', 'RARE'])
})

test('setIntegrity separates unresolved ids from unloaded files and counts recipes', () => {
  const resolved = [
    { ...row('m1', 'TP01', 't1'), recipeName: 'RCP_A' },
    { ...row('m2', 'TP02', 't2'), recipeName: 'RCP_B' }
  ]
  const files = new Map<string, OptionFileInput>([['m1', optFile(['WAFER'], [])]])
  const out = setIntegrity(['m1', 'm2', 'ghost'], resolved, files)
  assert.equal(out.requested, 3)
  assert.equal(out.resolved, 2)
  assert.equal(out.loaded, 1)
  assert.deepEqual(out.unresolvedMsrs, ['ghost'])
  assert.equal(out.recipeCount, 2)
})

test('setIntegrity on a clean single-recipe set reports nothing to warn about', () => {
  const resolved = [
    { ...row('m1', 'TP01', 't1'), recipeName: 'RCP_A' },
    { ...row('m2', 'TP02', 't2'), recipeName: 'RCP_A' }
  ]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['WAFER'], [])], ['m2', optFile(['WAFER'], [])]
  ])
  const out = setIntegrity(['m1', 'm2'], resolved, files)
  assert.deepEqual(out.unresolvedMsrs, [])
  assert.equal(out.recipeCount, 1)
  assert.equal(out.loaded, 2)
})

test('setIntegrity counts loaded as RESOLVED rows with a file, not the size of the files map', () => {
  const resolved = [
    { ...row('m1', 'TP01', 't1'), recipeName: 'RCP_A' },
    { ...row('m2', 'TP02', 't2'), recipeName: 'RCP_A' }
  ]
  // 'stale' is in the files map but is NOT part of the resolved set — a map
  // left over from a previous set. files.size would say 2; only m1 is loaded.
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['WAFER'], [])],
    ['stale', optFile(['WAFER'], [])]
  ])
  assert.equal(setIntegrity(['m1', 'm2'], resolved, files).loaded, 1)
})

test('setParamOptions breaks an equal coverage AND equal MP-order tie by name', () => {
  // Both parameters come from the same measurement at the same (mp_number,
  // sequence) — an unusual recipe, but it isolates the name comparator: with
  // coverage and rank tied, only localeCompare can decide the order.
  const rows = [row('m1', 'TP01', 't1')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['Z_LATE', 'A_FIRST'], [
      { parameter: 'Z_LATE', mp_number: 1, sequence: 1 },
      { parameter: 'A_FIRST', mp_number: 1, sequence: 1 }
    ])]
  ])
  assert.deepEqual(setParamOptions(rows, files).map(o => o.parameter), ['A_FIRST', 'Z_LATE'])
})

test('setParamOptions sorts an unranked parameter last within its coverage tier, and ignores negative-mp_number rows when ranking', () => {
  // RANKED has a real MP row (mp_number 2). UNRANKED's only row has a negative
  // mp_number, which must be excluded from ranking — if it were not excluded,
  // -1 would sort BEFORE 2 and UNRANKED would wrongly come first. Correctly
  // excluded, UNRANKED has no rank at all and falls back to the NO_RANK
  // sentinel, which sorts last within the (tied) coverage tier.
  const rows = [row('m1', 'TP01', 't1')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['RANKED', 'UNRANKED'], [
      { parameter: 'RANKED', mp_number: 2, sequence: 1 },
      { parameter: 'UNRANKED', mp_number: -1, sequence: 1 }
    ])]
  ])
  assert.deepEqual(setParamOptions(rows, files).map(o => o.parameter), ['RANKED', 'UNRANKED'])
})
