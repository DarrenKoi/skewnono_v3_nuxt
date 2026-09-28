// Pure-logic tests — run with: npm --prefix frontend test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseFdcValues, contactpinState, contactpinRows, spmDeviationSeries, fdcDailyMeans, type LaserPowerValue, type SpmVoltagesValue, type ContactpinValue } from './fdcValues.ts'

test('TemperatureEChuck → position + temp', () => {
  const p = parseFdcValues(['TemperatureEChuck', '0', '1', '23.39053'])
  assert.deepEqual(p, { key: 'TemperatureEChuck', data: { position: '1', temp: 23.39053 } })
})

test('LaserPower → two xy pairs', () => {
  const p = parseFdcValues(['LaserPower', '0', '0.78', '0.73', '341990938', '46504250'])
  assert.equal(p.key, 'LaserPower')
  assert.deepEqual((p.data as LaserPowerValue).pairs, [{ x: 0.78, y: 0.73 }, { x: 341990938, y: 46504250 }])
})

test('SPMVoltages → channel, fit model, numeric profile after fit model', () => {
  const p = parseFdcValues(['SPMVoltages', '0', 'B', '7', '1', '1', 'spline', '-0.2', '0', '-0.4'])
  assert.equal(p.key, 'SPMVoltages')
  assert.equal((p.data as SpmVoltagesValue).channel, 'B')
  assert.equal((p.data as SpmVoltagesValue).fitModel, 'spline')
  assert.deepEqual((p.data as SpmVoltagesValue).profile, [-0.2, 0, -0.4])
})

test('SPMVoltages without a fit-model token (CG5000) → profile starts after the header', () => {
  const p = parseFdcValues(['SPMVoltages', '0', 'A', '7', '1', '1', '-0.2', '0', '-0.4'])
  assert.deepEqual(p.data, { channel: 'A', fitModel: '', profile: [-0.2, 0, -0.4] })
})

test('ContactpinConductionInfo → channel, judgment, 5 values', () => {
  const p = parseFdcValues(['ContactpinConductionInfo', '0', 'A', '5', 'NotConduction', '-25.5', '-0.9', '24.6', '25.0', '182501'])
  assert.equal(p.key, 'ContactpinConductionInfo')
  assert.equal((p.data as ContactpinValue).channel, 'A')
  assert.equal((p.data as ContactpinValue).judgment, 'NotConduction')
  assert.deepEqual((p.data as ContactpinValue).values, [-25.5, -0.9, 24.6, 25.0, 182501])
})

test('contactpin states, spread, per-channel daily rate, first row and reset', () => {
  const doc = (timestamp: string, channel: string, judgment: string, values: number[]) => ({
    timestamp, values: ['ContactpinConductionInfo', '0', channel, '5', judgment, ...values]
  })
  const rows = contactpinRows([
    doc('2026-09-29T00:00:00', 'A', 'NotConduction', [0, 10, 20, 38, 2]),
    doc('2026-09-28T12:00:00', 'B', 'UnstableConduction', [0, 1, 2, 3, 50]),
    doc('2026-09-28T00:00:00', 'A', 'Conduction', [0, 2, 4, 6.4, 1]),
    doc('2026-09-30T00:00:00', 'A', 'Mystery', [0, 1, 2, 3, 0])
  ])
  assert.deepEqual(rows.map(r => r.state), ['ok', 'warn', 'bad', 'unknown'])
  assert.deepEqual(rows.map(r => r.rate), [null, null, 1, null])
  assert.deepEqual(rows.map(r => r.spread), [6.4, 3, 38, 3])
  assert.deepEqual(rows[0]?.values, [0, 2, 4, 6.4])
  assert.equal(contactpinState('NonConduction'), 'unknown') // the real spelling is 'Not' (user-confirmed 2026-09-29)
  assert.equal(contactpinRows([doc('2026-09-28T00:00:00', 'A', 'Conduction', [0, 1, 2, 3, 1]), doc('2026-09-28T00:00:00', 'A', 'Conduction', [0, 1, 2, 3, 2])])[1]?.rate, null)
})

test('SPM channel median profile and RMS skip mismatched lengths', () => {
  const doc = (timestamp: string, channel: string, profile: number[]) => ({
    timestamp, values: ['SPMVoltages', '0', channel, '7', 'spline', ...profile]
  })
  const series = spmDeviationSeries([
    doc('2026-09-28T00:00:00', 'A', [0, 2]),
    doc('2026-09-29T00:00:00', 'A', [2, 4]),
    doc('2026-09-30T00:00:00', 'A', [20]),
    doc('2026-09-28T00:00:00', 'B', [5, 5])
  ])
  assert.deepEqual(series[0]?.points.map(p => p.value), [1, 1])
  assert.equal(series[0]?.points.length, 2)
  assert.deepEqual(series[1]?.points.map(p => p.value), [0])
})

test('daily mean pools positions by calendar day and places point at noon', () => {
  assert.deepEqual(fdcDailyMeans([
    { ts: '2026-09-28T00:01:00', value: 23 },
    { ts: '2026-09-28T00:01:20', value: 25 },
    { ts: '2026-09-29T00:00:00', value: 26 }
  ]), [
    { ts: '2026-09-28T12:00:00', value: 24 },
    { ts: '2026-09-29T12:00:00', value: 26 }
  ])
})

test('ContactpinConductionInfo → comma decimal read positionally, counter stays last', () => {
  const p = parseFdcValues(['ContactpinConductionInfo', '0', 'A', '5', 'NotConduction', '-25.5', '-0.9', '24.6', '25,0', '182501'])
  assert.deepEqual((p.data as ContactpinValue).values, [-25.5, -0.9, 24.6, 25.0, 182501])
  const [row] = contactpinRows([{ timestamp: '2026-05-01T00:00:00', values: ['ContactpinConductionInfo', '0', 'A', '5', 'NotConduction', '-25.5', '-0.9', '24.6', 'x', '182501'] }])
  // An unreadable margin cell leaves no spread, but never shifts the counter into the margin.
  assert.equal(row!.spread, null)
  assert.deepEqual(row!.values.slice(0, 3), [-25.5, -0.9, 24.6])
})

test('unknown key → data null', () => {
  const p = parseFdcValues(['Mystery', '0', '1'])
  assert.deepEqual(p, { key: 'Mystery', data: null })
})
