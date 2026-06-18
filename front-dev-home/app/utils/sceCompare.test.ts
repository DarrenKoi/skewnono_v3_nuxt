// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { flattenSettings, compareSettings, coefficientSeries } from './sceCompare.ts'

const eqpA = {
  SemCond: { SemCond_Vacc: '800', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  Coefficients: [{ index: 0, values: [0.00884, 0.964293] }, { index: 2, values: [0.01, 0.97] }]
}
const eqpB = {
  SemCond: { SemCond_Vacc: '500', SemCond_Ip: '8.0000' },
  ImgCond: { ImgCond_Mag: ['150003298', '150003298'] },
  SCEParam: { SCEParam_SmoothRadius: '7' },
  Coefficients: []
}

test('flattenSettings: dotted leaf paths, arrays joined, Coefficients skipped', () => {
  const flat = flattenSettings(eqpA)
  assert.equal(flat['SemCond.SemCond_Vacc'], '800')
  assert.equal(flat['ImgCond.ImgCond_Mag'], '150003298,150003298')
  assert.ok(!Object.keys(flat).some(k => k.startsWith('Coefficients')))
})

test('compareSettings: flags only the differing Vacc row', () => {
  const rows = compareSettings({ A: eqpA, B: eqpB }, 'A')
  const vacc = rows.find(r => r.path === 'SemCond.SemCond_Vacc')!
  assert.equal(vacc.selected, '800')
  assert.equal(vacc.siblings['B'], '500')
  assert.equal(vacc.differs, true)

  const ip = rows.find(r => r.path === 'SemCond.SemCond_Ip')!
  assert.equal(ip.differs, false)
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
