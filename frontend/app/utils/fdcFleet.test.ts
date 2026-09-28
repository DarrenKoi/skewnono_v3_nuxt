import assert from 'node:assert/strict'
import test from 'node:test'
import type { FdcFleetTool } from '../composables/useHardwareApi.ts'
import { fdcFleetHeatmap, fdcFleetLaserRows, fdcFleetPinRows, fdcFleetHistogram, fdcFleetCounterRows } from './fdcFleet.ts'

const tool = (eqp_id: string, values: Partial<FdcFleetTool> = {}): FdcFleetTool => ({
  eqp_id, eqp_model_cd: null, temp_c: null, temp_days: [], laser_x1: null, laser_y1: null,
  pin_counts: {}, counter_rates: [], ...values
})

test('heatmap sorts hot tools first and days chronologically, omitting tools without temperatures', () => {
  const result = fdcFleetHeatmap([
    tool('cold', { temp_c: 22, temp_days: [{ day: '2026-05-02', temp_c: 22 }] }),
    tool('empty'),
    tool('hot', { temp_c: 24, temp_days: [{ day: '2026-05-01', temp_c: 24 }] })
  ])
  assert.deepEqual(result.tools, ['hot', 'cold'])
  assert.deepEqual(result.days, ['2026-05-01', '2026-05-02'])
  assert.deepEqual(result.points, [[0, 0, 24], [1, 1, 22]])
  assert.deepEqual(fdcFleetHeatmap([tool('empty')]).points, [])
})

test('laser ranking skips missing x1 and retains missing y1', () => {
  assert.deepEqual(fdcFleetLaserRows([
    tool('a', { laser_x1: 0.7 }), tool('b'), tool('c', { laser_x1: 0.9, laser_y1: 0.8 })
  ]), [{ eqpId: 'c', x1: 0.9, y1: 0.8 }, { eqpId: 'a', x1: 0.7, y1: null }])
})

test('pin rows exclude zero totals and rank by Conduction share, not raw count', () => {
  const rows = fdcFleetPinRows([
    tool('good', { pin_counts: { Conduction: 9, UnstableConduction: 1, NonConduction: 0 } }),
    tool('empty'),
    tool('bad', { pin_counts: { Conduction: 1, UnstableConduction: 1, NonConduction: 2 } })
  ])
  assert.deepEqual(rows.map(row => row.eqpId), ['bad', 'good'])
  assert.equal(rows[0]?.greenRate, 0.25)
  assert.equal(rows[1]?.greenRate, 0.9)
  assert.deepEqual(rows[0]?.percent, { ok: 25, warn: 25, bad: 50 })
})

test('histogram sorts bins and fills absent judgments with zero', () => {
  const result = fdcFleetHistogram({ tools: [], spread_bin_width: 2, spread_bins: [
    { judgment: 'Conduction', lo: 6, count: 3 }, { judgment: 'NonConduction', lo: 4, count: 2 }
  ] })
  assert.deepEqual(result.labels, ['4–6', '6–8'])
  assert.deepEqual(result.series.map(series => series.counts), [[0, 3], [0, 0], [2, 0]])
  assert.deepEqual(result.series[2]?.points, [[5, 2], [7, 0]])
})

test('counter rates sort descending with null last', () => {
  const rows = fdcFleetCounterRows([
    tool('a', { counter_rates: [{ channel: 'A', per_day: null }, { channel: 'B', per_day: 2 }] }),
    tool('b', { counter_rates: [{ channel: 'C', per_day: 4 }] })
  ])
  assert.deepEqual(rows.map(row => row.per_day), [4, 2, null])
  assert.deepEqual(fdcFleetCounterRows([tool('empty')]), [])
})
