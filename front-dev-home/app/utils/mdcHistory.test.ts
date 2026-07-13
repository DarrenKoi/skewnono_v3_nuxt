// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildMdcFamilies, trajectoryPoints } from './mdcHistory.ts'

const doc = (ts: string, cond: string, value: number) =>
  ({ timestamp: ts, beam_condition: cond, mdc_value: value })

const docs = [
  doc('2026-06-01 09:00', '800V_HR_0Deg', 1.001),
  doc('2026-06-01 09:00', '800V_HR_90Deg', 0.999),
  doc('2026-06-01 09:00', 'Valley', 1.002),
  doc('2026-06-08 10:00', '800V_HR_0Deg', 1.003),
  doc('2026-06-08 10:00', '800V_HR_90Deg', 0.998),
  doc('2026-06-08 10:00', 'Valley', 1.004)
]

test('buildMdcFamilies: groups by family and splits 0/90 axes', () => {
  const fams = buildMdcFamilies(docs)
  assert.deepEqual(fams.map(f => f.key), ['800V_HR', 'Valley'])
  const f800 = fams[0]!
  assert.equal(f800.zero.length, 2)
  assert.equal(f800.ninety.length, 2)
  assert.deepEqual(f800.zero[0], { ts: '2026-06-01 09:00', value: 1.001 })
})

test('buildMdcFamilies: unpaired condition lands in zero with empty ninety', () => {
  const valley = buildMdcFamilies(docs)[1]!
  assert.equal(valley.zero.length, 2)
  assert.equal(valley.ninety.length, 0)
})

test('buildMdcFamilies: points come out ascending even from shuffled docs', () => {
  const fams = buildMdcFamilies([...docs].reverse())
  const ts = fams.find(f => f.key === '800V_HR')!.zero.map(p => p.ts)
  assert.deepEqual(ts, [...ts].sort())
})

test('buildMdcFamilies: non-numeric values and blank conditions are dropped', () => {
  const fams = buildMdcFamilies([
    doc('2026-06-01 09:00', '800V_HR_0Deg', NaN),
    { timestamp: '2026-06-01 09:00', beam_condition: '', mdc_value: 1 },
    doc('2026-06-02 09:00', '800V_HR_0Deg', 1.002)
  ])
  assert.equal(fams.length, 1)
  assert.equal(fams[0]!.zero.length, 1)
})

test('trajectoryPoints: zips 0/90 by timestamp, skipping unmatched events', () => {
  const f800 = buildMdcFamilies(docs)[0]!
  assert.deepEqual(trajectoryPoints(f800), [
    { ts: '2026-06-01 09:00', x: 1.001, y: 0.999 },
    { ts: '2026-06-08 10:00', x: 1.003, y: 0.998 }
  ])
})

test('trajectoryPoints: unpaired family yields no points', () => {
  const valley = buildMdcFamilies(docs)[1]!
  assert.deepEqual(trajectoryPoints(valley), [])
})
