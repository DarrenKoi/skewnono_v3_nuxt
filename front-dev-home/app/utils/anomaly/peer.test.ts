// front-dev-home/app/utils/anomaly/peer.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { peerVerdicts } from './peer.ts'
import { DEFAULT_METHOD_CONFIG, type MethodConfig } from './types.ts'

const rangeCfg: MethodConfig = DEFAULT_METHOD_CONFIG
const stddevCfg: MethodConfig = { ...DEFAULT_METHOD_CONFIG, method: 'stddev' }

test('below minN → all insufficient (length preserved)', () => {
  const v = peerVerdicts([10, 11], { config: rangeCfg, metric: 'mean' })
  assert.equal(v.length, 2)
  assert.ok(v.every(x => x.status === 'insufficient'))
})

test('clean series → all normal', () => {
  const v = peerVerdicts([10, 10, 10, 10, 10], { config: rangeCfg, metric: 'mean' })
  assert.ok(v.every(x => x.status === 'evaluated' && x.severity === 'normal'))
})

test('MASKING N=5: a true +20% outlier is abnormal thanks to LOO', () => {
  // Non-LOO (center includes the point) would show only +15.4% → missed.
  const v = peerVerdicts([10, 10, 10, 10, 12], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[4]!.severity, 'abnormal')
  assert.ok(v.slice(0, 4).every(x => x.severity === 'normal'))
})

test('MASKING N=15: lone outlier still abnormal under LOO', () => {
  const vals = Array(14).fill(10).concat([12])
  const v = peerVerdicts(vals, { config: rangeCfg, metric: 'mean' })
  assert.equal(v[14]!.severity, 'abnormal')
})

test('MASKING: two co-directional outliers both flagged (LOO)', () => {
  const v = peerVerdicts([10, 10, 10, 10, 10, 12.5, 12.5], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[5]!.severity, 'abnormal')
  assert.equal(v[6]!.severity, 'abnormal')
})

test('stddev method: lone extreme is flagged under LOO at N=7', () => {
  const v = peerVerdicts([50, 51, 49, 50, 52, 48, 90], { config: stddevCfg, metric: 'mean' })
  assert.equal(v[6]!.severity, 'abnormal')
  assert.equal(v[6]!.method, 'stddev')
  assert.equal(v[6]!.peerMean, 50)
  assert.ok(Math.abs(v[6]!.peerStd! - Math.sqrt(2)) < 1e-12)
})

test('verdict carries metric, signal=peer, and active method', () => {
  const v = peerVerdicts([10, 10, 10, 20], { config: rangeCfg, metric: 'spread', tag: '산포' })
  assert.equal(v[3]!.metric, 'spread')
  assert.equal(v[3]!.signal, 'peer')
  assert.equal(v[3]!.method, 'range')
  assert.match(v[3]!.reason, /산포/)
})

test('non-finite entries → that item insufficient, others evaluated', () => {
  const v = peerVerdicts([10, 10, 10, 10, NaN], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[4]!.status, 'insufficient')
  assert.ok(v.slice(0, 4).every(x => x.status === 'evaluated'))
})

test('effective N after excluding missing drops below minN → all insufficient', () => {
  const v = peerVerdicts([10, 10, NaN, NaN], { config: rangeCfg, metric: 'mean' })
  assert.ok(v.every(x => x.status === 'insufficient'))
})
