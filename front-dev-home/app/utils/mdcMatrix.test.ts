// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildMdcMatrix, cellDeviation } from './mdcMatrix.ts'

const settings = {
  ECX002: { '800V_HR_0Deg': '1.004', '500V_HR_0Deg': '1.0030' },
  ECX001: { '800V_HR_0Deg': '1.000', '500V_HR_0Deg': '1.0000', '3000V': '0.99' },
  ECX003: { '800V_HR_0Deg': '1.010' }
}

test('buildMdcMatrix: selected eqp is the first row; columns are the sorted union', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  assert.equal(m.tools[0], 'ECX001')
  assert.deepEqual(m.conditions, ['3000V', '500V_HR_0Deg', '800V_HR_0Deg'])
})

test('buildMdcMatrix: missing condition for a tool is null', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const rowECX003 = m.tools.indexOf('ECX003')
  const col3000 = m.conditions.indexOf('3000V')
  assert.equal(m.values[rowECX003]![col3000], null)
})

test('buildMdcMatrix: numeric strings parsed to numbers', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  assert.equal(m.values[0]![col800], 1.0) // ECX001 row
})

test('cellDeviation: selected tool deviates 0 from itself', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  assert.equal(cellDeviation(m, 0, col800), 0)
})

test('cellDeviation: sign follows direction, magnitude in [-1,1]', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const col800 = m.conditions.indexOf('800V_HR_0Deg')
  const rowECX003 = m.tools.indexOf('ECX003') // 1.010 vs baseline 1.000 → positive
  const dev = cellDeviation(m, rowECX003, col800)
  assert.ok(dev > 0 && dev <= 1)
})

test('cellDeviation: null cell → 0', () => {
  const m = buildMdcMatrix(settings, 'ECX001')
  const rowECX003 = m.tools.indexOf('ECX003')
  const col3000 = m.conditions.indexOf('3000V')
  assert.equal(cellDeviation(m, rowECX003, col3000), 0)
})
