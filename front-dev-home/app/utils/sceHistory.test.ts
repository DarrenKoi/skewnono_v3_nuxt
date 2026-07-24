// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sceCoeffIndexSeries, sceParamLabel, sceParamSeries, sceTrendKeys } from './sceHistory.ts'

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
