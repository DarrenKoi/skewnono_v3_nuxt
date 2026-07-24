// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  sceCoeffIndexSeries, sceCoeffRevisions, sceDocDates, sceLatestDates,
  sceParamLabel, sceParamSeries, sceRevisionLabel, sceTrendKeys
} from './sceHistory.ts'

const docs = [
  {
    date: '2026-07-17',
    FileInfo: { SharpCharFile: '/HITACHI/a.dat' },
    SCEParam: { SCEParam_SmoothRadius: '7', SCEParam_CorrCoefLimit: '0.20000' },
    SemCond: { SemCond_Vacc: '800', SemCond_Optics: 'High Reso.' },
    ImgCond: { ImgCond_Mag: ['150003298', '150003298'], ImgCond_FocusOffset: ['-2'] },
    Coefficients: [{ index: 0, values: [0.01, 0.95] }, { index: 1, values: [0.02, 0.96] }]
  },
  {
    date: '2026-07-22',
    FileInfo: { SharpCharFile: '/HITACHI/b.dat' },
    SCEParam: { SCEParam_SmoothRadius: '8', SCEParam_FitRangeSt: '40' },
    SemCond: { SemCond_Vacc: '800', SemCond_Optics: 'High Reso.' },
    ImgCond: { ImgCond_Mag: ['150003300', '150003300'], ImgCond_FocusOffset: ['-2'] },
    Coefficients: [{ index: 0, values: [0.015, 0.94] }, { index: 1, values: [0.021, 0.97] }]
  },
  // Malformed rows must drop out, not crash: no date / non-numeric / no block.
  { SCEParam: { SCEParam_SmoothRadius: '9' } },
  { date: '2026-07-24', SCEParam: { SCEParam_SmoothRadius: 'seven' } },
  { date: '2026-07-26' }
]

test('sceTrendKeys: numeric fields across all three blocks, block-ordered', () => {
  // FileInfo (paths) and non-numeric strings (SemCond_Optics) are excluded;
  // list-valued ImgCond fields count via their first element.
  assert.deepEqual(sceTrendKeys(docs), [
    { block: 'SCEParam', key: 'SCEParam_CorrCoefLimit', label: 'CorrCoefLimit' },
    { block: 'SCEParam', key: 'SCEParam_FitRangeSt', label: 'FitRangeSt' },
    { block: 'SCEParam', key: 'SCEParam_SmoothRadius', label: 'SmoothRadius' },
    { block: 'SemCond', key: 'SemCond_Vacc', label: 'Vacc' },
    { block: 'ImgCond', key: 'ImgCond_FocusOffset', label: 'FocusOffset' },
    { block: 'ImgCond', key: 'ImgCond_Mag', label: 'Mag' }
  ])
  assert.deepEqual(sceTrendKeys([]), [])
})

test('sceParamLabel: strips any block prefix, leaves bare keys alone', () => {
  assert.equal(sceParamLabel('SCEParam_SmoothRadius'), 'SmoothRadius')
  assert.equal(sceParamLabel('SemCond_Vacc'), 'Vacc')
  assert.equal(sceParamLabel('ImgCond_FocusOffset'), 'FocusOffset')
  assert.equal(sceParamLabel('Bare'), 'Bare')
})

test('sceParamSeries: resolves a key in whichever block holds it', () => {
  assert.deepEqual(sceParamSeries(docs, 'SCEParam_SmoothRadius'), [
    { ts: '2026-07-17', key: '2026-07-17', value: 7 },
    { ts: '2026-07-22', key: '2026-07-22', value: 8 }
  ])
  // SemCond config is flat across dates — a stable line, not a dropped series.
  assert.deepEqual(sceParamSeries(docs, 'SemCond_Vacc'), [
    { ts: '2026-07-17', key: '2026-07-17', value: 800 },
    { ts: '2026-07-22', key: '2026-07-22', value: 800 }
  ])
  // A key absent on some dates yields a shorter series, not NaN holes.
  assert.deepEqual(sceParamSeries(docs, 'SCEParam_FitRangeSt'), [
    { ts: '2026-07-22', key: '2026-07-22', value: 40 }
  ])
})

test('sceParamSeries: list-valued ImgCond fields use the first element', () => {
  assert.deepEqual(sceParamSeries(docs, 'ImgCond_Mag'), [
    { ts: '2026-07-17', key: '2026-07-17', value: 150003298 },
    { ts: '2026-07-22', key: '2026-07-22', value: 150003300 }
  ])
  assert.deepEqual(sceParamSeries(docs, 'ImgCond_FocusOffset'), [
    { ts: '2026-07-17', key: '2026-07-17', value: -2 },
    { ts: '2026-07-22', key: '2026-07-22', value: -2 }
  ])
})

test('sceDocDates: collection dates in doc order, dateless docs dropped', () => {
  assert.deepEqual(sceDocDates(docs), ['2026-07-17', '2026-07-22', '2026-07-24', '2026-07-26'])
  assert.deepEqual(sceDocDates([]), [])
})

test('sceLatestDates: the newest N, still ascending', () => {
  const dates = ['2026-07-17', '2026-07-22', '2026-07-24', '2026-07-26']
  assert.deepEqual(sceLatestDates(dates, 3), ['2026-07-22', '2026-07-24', '2026-07-26'])
  // Asking for more than exist yields everything, not padding.
  assert.deepEqual(sceLatestDates(dates, 9), dates)
  assert.deepEqual(sceLatestDates(dates, 0), [])
  assert.deepEqual(sceLatestDates([], 3), [])
})

const curve = (a: number, b: number) => [
  { index: 0, values: [a, b] },
  { index: 1, values: [a + 0.01, b + 0.01] }
]

test('sceCoeffRevisions: consecutive identical curves collapse into one run', () => {
  const held = [
    { date: '2026-05-02', Coefficients: curve(0.01, 0.95) },
    { date: '2026-05-04', Coefficients: curve(0.01, 0.95) },
    { date: '2026-05-06', Coefficients: curve(0.01, 0.95) },
    // A PM re-tune: new curve, new revision.
    { date: '2026-05-08', Coefficients: curve(0.02, 0.93) },
    { date: '2026-05-10', Coefficients: curve(0.02, 0.93) }
  ]
  assert.deepEqual(sceCoeffRevisions(held), [
    { date: '2026-05-02', through: '2026-05-06', dates: ['2026-05-02', '2026-05-04', '2026-05-06'] },
    { date: '2026-05-08', through: '2026-05-10', dates: ['2026-05-08', '2026-05-10'] }
  ])
  assert.deepEqual(sceCoeffRevisions([]), [])
})

test('sceCoeffRevisions: a revert is a new revision, not a re-join', () => {
  // Folding this back into the first entry would hide that the value moved
  // away and came back — the most interesting thing in the window.
  const reverted = [
    { date: '2026-05-02', Coefficients: curve(0.01, 0.95) },
    { date: '2026-05-04', Coefficients: curve(0.02, 0.93) },
    { date: '2026-05-06', Coefficients: curve(0.01, 0.95) }
  ]
  assert.deepEqual(sceCoeffRevisions(reverted).map(r => r.date), [
    '2026-05-02', '2026-05-04', '2026-05-06'
  ])
})

test('sceCoeffRevisions: a difference anywhere in the curve splits the run', () => {
  const docs = [
    { date: '2026-05-02', Coefficients: curve(0.01, 0.95) },
    // Same length, same indices, one value differs in the last entry.
    { date: '2026-05-04', Coefficients: [{ index: 0, values: [0.01, 0.95] }, { index: 1, values: [0.02, 0.9999] }] }
  ]
  assert.equal(sceCoeffRevisions(docs).length, 2)
  // Differing index sets, differing lengths, and malformed curves never merge.
  assert.equal(sceCoeffRevisions([
    { date: '2026-05-02', Coefficients: curve(0.01, 0.95) },
    { date: '2026-05-04', Coefficients: [{ index: 9, values: [0.01, 0.95] }, { index: 1, values: [0.02, 0.96] }] }
  ]).length, 2)
  assert.equal(sceCoeffRevisions([
    { date: '2026-05-02', Coefficients: [] },
    { date: '2026-05-04', Coefficients: [] }
  ]).length, 1)
  assert.equal(sceCoeffRevisions([
    { date: '2026-05-02', Coefficients: 'nope' },
    { date: '2026-05-04', Coefficients: 'nope' }
  ]).length, 2)
})

test('sceCoeffRevisions: dateless docs are skipped, not merged blindly', () => {
  const docs = [
    { date: '2026-05-02', Coefficients: curve(0.01, 0.95) },
    { Coefficients: curve(0.5, 0.5) },
    { date: '2026-05-06', Coefficients: curve(0.01, 0.95) }
  ]
  // The undated doc contributes no date; the two dated ones still carry the
  // same curve, so they stay one revision.
  assert.deepEqual(sceCoeffRevisions(docs), [
    { date: '2026-05-02', through: '2026-05-06', dates: ['2026-05-02', '2026-05-06'] }
  ])
})

test('sceRevisionLabel: single date bare, run shows span and count', () => {
  assert.equal(
    sceRevisionLabel({ date: '2026-05-08', through: '2026-05-08', dates: ['2026-05-08'] }),
    '2026-05-08'
  )
  assert.equal(
    sceRevisionLabel({ date: '2026-05-02', through: '2026-05-24', dates: ['a', 'b', 'c'] }),
    '2026-05-02 ~ 05-24 · 3회'
  )
  // A span across new year keeps the end year — dropping it would read as
  // an 11-month-earlier date.
  assert.equal(
    sceRevisionLabel({ date: '2025-12-28', through: '2026-01-06', dates: ['a', 'b'] }),
    '2025-12-28 ~ 2026-01-06 · 2회'
  )
})

test('sceCoeffIndexSeries: values[0]/values[1] at one index across dates', () => {
  assert.deepEqual(sceCoeffIndexSeries(docs, 1), {
    v0: [
      { ts: '2026-07-17', key: '2026-07-17', value: 0.02 },
      { ts: '2026-07-22', key: '2026-07-22', value: 0.021 }
    ],
    v1: [
      { ts: '2026-07-17', key: '2026-07-17', value: 0.96 },
      { ts: '2026-07-22', key: '2026-07-22', value: 0.97 }
    ]
  })
  // An index the archive never carries is empty, not NaN-filled.
  assert.deepEqual(sceCoeffIndexSeries(docs, 359), { v0: [], v1: [] })
  assert.deepEqual(sceCoeffIndexSeries([], 0), { v0: [], v1: [] })
})
