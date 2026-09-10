// Pure-logic tests for paraTrendSeries. Zero deps:
//   node --test app/utils/paraTrendSeries.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  PARA_KEYS, extractParaTrend, formatTrendTick, paraLabel,
  type ParaCounts, type ParaTrendInput
} from './paraTrendSeries.ts'

// --- fixtures ---

const row = (lot: string, p16: number, p13: number, p9: number, p5: number): ParaCounts => ({
  lot_cd: lot, para_16: p16, para_13: p13, para_9: p9, para_5: p5
})

// NOTE: `row()` deliberately omits `para_over_16`, so every fixture below is a
// pre-2026-08-10 weekly snapshot — the shape the trend view still reads for up
// to eight weeks after the range split. The bucket has to read as 0 there, not
// as `undefined` poisoning the totals.

// Two dates, two lots. LOT_B is absent on the second date on purpose.
const trend: ParaTrendInput = {
  dates: ['2026-07-20', '2026-07-27'],
  trend: {
    '2026-07-20': {
      all_summary: [row('LOT_A', 10, 20, 30, 40), row('LOT_B', 1, 2, 3, 4)],
      only_sample_summary: [row('LOT_A', 1, 1, 1, 1)]
    },
    '2026-07-27': {
      all_summary: [row('LOT_A', 12, 22, 33, 44)],
      only_sample_summary: [row('LOT_A', 2, 2, 2, 2)]
    }
  }
}

// --- counts stay absolute (the whole point of this module) ---

test('emits the raw counts, unnormalised', () => {
  const { series } = extractParaTrend(trend, 'all_summary', 'LOT_A')
  const byKey = Object.fromEntries(series.map(s => [s.key, s.values]))

  assert.deepEqual(byKey.para_16, [10, 12])
  assert.deepEqual(byKey.para_13, [20, 22])
  assert.deepEqual(byKey.para_9, [30, 33])
  assert.deepEqual(byKey.para_5, [40, 44])
})

test('doubling every para doubles every emitted value', () => {
  // Guards against per-date normalisation creeping back: under the old
  // composition maths this scaling was invisible, every value staying at its
  // same share of the daily total.
  const doubled: ParaTrendInput = {
    dates: ['2026-07-20'],
    trend: { '2026-07-20': { all_summary: [row('LOT_A', 20, 40, 60, 80)] } }
  }
  const base = extractParaTrend(trend, 'all_summary', 'LOT_A')
  const twice = extractParaTrend(doubled, 'all_summary', 'LOT_A')

  for (const key of PARA_KEYS) {
    const b = base.series.find(s => s.key === key)!.values[0] as number
    const t = twice.series.find(s => s.key === key)!.values[0] as number
    assert.equal(t, b * 2, `${key} should scale with the data`)
  }
})

test('a series is never rescaled to its own maximum', () => {
  // The old lines mode divided each para by its own max, so every series ended
  // at 1.0 regardless of magnitude. para_5 must stay 4x para_16 here.
  const { series } = extractParaTrend(trend, 'all_summary', 'LOT_A')
  const p16 = series.find(s => s.key === 'para_16')!.values[0] as number
  const p5 = series.find(s => s.key === 'para_5')!.values[0] as number
  assert.equal(p5 / p16, 4)
})

// --- stack total ---

test('totals equal the sum of every bucket', () => {
  const { totals } = extractParaTrend(trend, 'all_summary', 'LOT_A')
  assert.deepEqual(totals, [100, 111])
})

test('totals are null, not zero, where the lot has no row', () => {
  const { totals } = extractParaTrend(trend, 'all_summary', 'LOT_B')
  assert.deepEqual(totals, [10, null])
})

// --- gaps ---

test('a missing date is a gap, not a zero', () => {
  const { series, hasData } = extractParaTrend(trend, 'all_summary', 'LOT_B')
  assert.equal(hasData, true)
  assert.deepEqual(series.find(s => s.key === 'para_16')!.values, [1, null])
})

test('an unknown lot yields no data but keeps one series per bucket', () => {
  const out = extractParaTrend(trend, 'all_summary', 'LOT_NOPE')
  assert.equal(out.hasData, false)
  assert.equal(out.series.length, PARA_KEYS.length)
  assert.deepEqual(out.series[0]!.values, [null, null])
})

test('null trend, null lot and unknown bucket are all handled', () => {
  for (const out of [
    extractParaTrend(null, 'all_summary', 'LOT_A'),
    extractParaTrend(undefined, 'all_summary', 'LOT_A'),
    extractParaTrend(trend, 'all_summary', null)
  ]) {
    assert.equal(out.hasData, false)
    assert.deepEqual(out.dates, [])
    assert.equal(out.series.length, PARA_KEYS.length)
  }

  // An unknown bucket still has dates — it just has no rows in them.
  const badBucket = extractParaTrend(trend, 'no_such_summary', 'LOT_A')
  assert.equal(badBucket.hasData, false)
  assert.deepEqual(badBucket.dates, ['2026-07-20', '2026-07-27'])
})

test('reads the bucket it is asked for', () => {
  const sample = extractParaTrend(trend, 'only_sample_summary', 'LOT_A')
  assert.deepEqual(sample.totals, [4, 8])
})

// --- series order ---

test('series come back in PARA_KEYS order, heaviest first', () => {
  const { series } = extractParaTrend(trend, 'all_summary', 'LOT_A')
  assert.deepEqual(
    series.map(s => s.key),
    ['para_over_16', 'para_16', 'para_13', 'para_9', 'para_5']
  )
})

// --- labels / ticks ---

test('labels name the RANGE, not the bucket key', () => {
  // `p16` read as "16 points". Since 2026-08-10 the bucket is 13 < x <= 16, so
  // the old label asserted a boundary that is no longer true.
  assert.equal(paraLabel('para_16'), '14–16')
  assert.equal(paraLabel('para_5'), '≤5')
  assert.equal(paraLabel('para_over_16'), '>16')
})

test('every bucket has a label and none repeat', () => {
  const labels = PARA_KEYS.map(paraLabel)
  assert.equal(labels.filter(Boolean).length, PARA_KEYS.length)
  assert.equal(new Set(labels).size, PARA_KEYS.length)
})

// --- pre-split snapshots ---

test('a snapshot without para_over_16 reads it as 0, not NaN', () => {
  // The fixtures have no such key. If it were read straight through, `totals`
  // would be NaN for every date and the stacked area would vanish silently.
  const { series, totals } = extractParaTrend(trend, 'all_summary', 'LOT_A')
  assert.deepEqual(series.find(s => s.key === 'para_over_16')!.values, [0, 0])
  assert.deepEqual(totals, [100, 111])
})

test('a snapshot WITH para_over_16 counts it in the total', () => {
  const withOver: ParaTrendInput = {
    dates: ['2026-08-10'],
    trend: {
      '2026-08-10': {
        all_summary: [{ ...row('LOT_A', 10, 20, 30, 40), para_over_16: 5 }]
      }
    }
  }
  const { series, totals } = extractParaTrend(withOver, 'all_summary', 'LOT_A')
  assert.deepEqual(series.find(s => s.key === 'para_over_16')!.values, [5])
  assert.deepEqual(totals, [105])
})

test('ticks render MM/DD and pass through anything else', () => {
  assert.equal(formatTrendTick('2026-07-20'), '07/20')
  assert.equal(formatTrendTick('week 3'), 'week 3')
})
