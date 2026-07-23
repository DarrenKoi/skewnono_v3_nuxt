// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseFdcValues, type LaserPowerValue, type SpmVoltagesValue, type ContactpinValue } from './fdcValues.ts'

test('TemperatureEChuck → position + temp', () => {
  const p = parseFdcValues(['TemperatureEChuck', '0', '1', '23.39053'])
  assert.deepEqual(p, { key: 'TemperatureEChuck', data: { position: '1', temp: 23.39053 } })
})

test('LaserPower → two xy pairs', () => {
  const p = parseFdcValues(['LaserPower', '0', '0.78', '0.73', '341990938', '46504250'])
  assert.equal(p.key, 'LaserPower')
  assert.deepEqual((p.data as LaserPowerValue).pairs, [{ x: 0.78, y: 0.73 }, { x: 341990938, y: 46504250 }])
})

test('SPMVoltages → channel, judgment, numeric profile after judgment', () => {
  const p = parseFdcValues(['SPMVoltages', '0', 'B', '7', '1', '1', 'spline', '-0.2', '0', '-0.4'])
  assert.equal(p.key, 'SPMVoltages')
  assert.equal((p.data as SpmVoltagesValue).channel, 'B')
  assert.equal((p.data as SpmVoltagesValue).judgment, 'spline')
  assert.deepEqual((p.data as SpmVoltagesValue).profile, [-0.2, 0, -0.4])
})

test('ContactpinConductionInfo → channel, judgment, 5 values', () => {
  const p = parseFdcValues(['ContactpinConductionInfo', '0', 'A', '5', 'NotConduction', '-25.5', '-0.9', '24.6', '25.0', '182501'])
  assert.equal(p.key, 'ContactpinConductionInfo')
  assert.equal((p.data as ContactpinValue).channel, 'A')
  assert.equal((p.data as ContactpinValue).judgment, 'NotConduction')
  assert.deepEqual((p.data as ContactpinValue).values, [-25.5, -0.9, 24.6, 25.0, 182501])
})

test('unknown key → data null', () => {
  const p = parseFdcValues(['Mystery', '0', '1'])
  assert.deepEqual(p, { key: 'Mystery', data: null })
})
