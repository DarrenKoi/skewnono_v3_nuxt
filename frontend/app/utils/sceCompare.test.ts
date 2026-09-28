// Pure-logic tests — run with: npm --prefix frontend test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { flattenSettings, compareSettings, coefficientSeries, sceHarmonics, sceHarmonicRows, SCE_FLEET_CONSTANT_FIELDS } from './sceCompare.ts'

const eqpA = {
  SemCond: { SemCond_Vacc: '800', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  FileInfo: { BaseSharpCharFile: '/shared/base', SharpCharFile: '/tool/A' },
  Coefficients: [{ index: 0, values: [0.00884, 0.964293] }, { index: 2, values: [0.01, 0.97] }]
}
const eqpB = {
  SemCond: { SemCond_Vacc: '500', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  FileInfo: { BaseSharpCharFile: '/shared/base', SharpCharFile: '/tool/B' },
  Coefficients: []
}

test('flattenSettings: dotted leaf paths, arrays joined, Coefficients skipped', () => {
  const flat = flattenSettings(eqpA)
  assert.equal(flat['SemCond.SemCond_Vacc'], '800')
  assert.equal(flat['ImgCond.ImgCond_Mag'], '150003298,150003298')
  // FileInfo is the compare table's own row (see compareSettings), not a setting.
  assert.ok(!Object.keys(flat).some(k => k.startsWith('FileInfo')))
  assert.ok(!Object.keys(flat).some(k => k.startsWith('Coefficients')))
})

test('compareSettings: flags only the differing Vacc row', () => {
  const rows = compareSettings({ A: eqpA, B: eqpB }, 'A')
  const vacc = rows.find(r => r.path === 'SemCond.SemCond_Vacc')!
  assert.equal(vacc.selected, '800')
  assert.equal(vacc.siblings['B'], '500')
  assert.equal(vacc.differs, true)

  assert.ok(!rows.some(r => r.path === 'SemCond.SemCond_Ip'))
  assert.ok(!rows.some(r => r.path === 'SCEParam.SCEParam_SmoothRadius'))
  assert.equal(rows.find(r => r.path === 'FileInfo.BaseSharpCharFile')?.selected, '/shared/base')
})

test('fleet-constant setting is retained when a shown tool differs', () => {
  assert.equal(SCE_FLEET_CONSTANT_FIELDS.size, 12)
  const changed = { ...eqpB, SemCond: { ...eqpB.SemCond, SemCond_Ip: '9.0000' } }
  assert.equal(compareSettings({ A: eqpA, B: changed }, 'A')[0]?.path, 'FileInfo.BaseSharpCharFile')
  assert.equal(compareSettings({ A: eqpA, B: changed }, 'A').find(r => r.path === 'SemCond.SemCond_Ip')?.differs, true)
  assert.ok(!compareSettings({ A: eqpA, B: changed }, 'A', []).some(r => r.path === 'SemCond.SemCond_Ip'))
})

test('compareSettings: compareIds scopes siblings + differs to picked tools', () => {
  const eqpC = { ...eqpB, SemCond: { SemCond_Vacc: '800', SemCond_Ip: '8.0000' } }
  // B differs on Vacc, C matches A. Scoping to [C] should hide B and clear differs.
  const rows = compareSettings({ A: eqpA, B: eqpB, C: eqpC }, 'A', ['C'])
  const vacc = rows.find(r => r.path === 'SemCond.SemCond_Vacc')!
  assert.deepEqual(Object.keys(vacc.siblings), ['C'])
  assert.equal(vacc.siblings['C'], '800')
  assert.equal(vacc.differs, false)
})

test('compareSettings: empty compareIds → no sibling columns', () => {
  const rows = compareSettings({ A: eqpA, B: eqpB }, 'A', [])
  assert.ok(rows.every(r => Object.keys(r.siblings).length === 0))
  assert.ok(rows.every(r => r.differs === false))
})

test('coefficientSeries: dense 360-length arrays, gaps NaN', () => {
  const { v0, v1 } = coefficientSeries(eqpA)
  assert.equal(v0.length, 360)
  assert.equal(v0[0], 0.00884)
  assert.equal(v1[2], 0.97)
  assert.ok(Number.isNaN(v0[1]))
})

test('coefficientSeries: undefined eqp → all-NaN 360 arrays', () => {
  const { v0 } = coefficientSeries(undefined)
  assert.equal(v0.length, 360)
  assert.ok(v0.every(Number.isNaN))
})

test('harmonics: order-2 sine has the expected amplitude and variance share', () => {
  const curve = Array.from({ length: 360 }, (_, i) => 3 + 0.4 * Math.sin(2 * Math.PI * 2 * i / 360))
  const result = sceHarmonics(curve)
  assert.ok(Math.abs(result.mean - 3) < 1e-10)
  assert.ok(Math.abs(result.amp[1]! - 0.4) < 1e-10)
  assert.ok(Math.abs(result.share - 1) < 1e-10)
  assert.equal(sceHarmonics(Array(360).fill(3)).share, 0)
  assert.ok(Number.isNaN(sceHarmonics([]).share))
  assert.ok(Number.isNaN(sceHarmonics([1, NaN]).mean))
})

test('harmonic rows pin selected tool and add fab medians', () => {
  const curve = (value: number) => ({ Coefficients: Array.from({ length: 360 }, (_, index) => ({ index, values: [value, 0] })) })
  const rows = sceHarmonicRows({ C: curve(3), A: curve(1), B: curve(2) }, 'B')
  assert.deepEqual(rows.map(r => r.id), ['B', 'A', 'C', 'fab 중앙값'])
  assert.equal(rows[3]?.mean, 2)
})
