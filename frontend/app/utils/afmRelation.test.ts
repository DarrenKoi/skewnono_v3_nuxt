// Pure-logic tests for afmRelation. Run: node --test app/utils/afmRelation.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailPayload, AfmDetailRow } from '~/composables/useAfmDetailApi'
import { relationColumns, relationSamples, relationState, relationSummary } from './afmRelation.ts'
import { prepareEntries } from './afmTrend.ts'

const L = 'Left_H (nm)'
const R = 'Right_H (nm)'

const row = (point: string, values: Record<string, unknown>, extra: Record<string, unknown> = {}): AfmDetailRow => ({
  measurement_point: point,
  Site: 'A',
  State: 'COMPLETED',
  Valid: true,
  ...values,
  ...extra
} as AfmDetailRow)

const entriesOf = (files: Record<string, AfmDetailRow[]>, recipe = 'VED_BS_TOP01') => prepareEntries(
  Object.entries(files).map(([filename, data], i) => ({
    source: { filename, recipeName: recipe, lotId: 'LOT1', slotNumber: 3, formattedDate: `2026-10-0${i + 1}` },
    payload: {
      filename, tool: 'MAP608', pickle_filename: `${filename}.pkl`, information: {}, summary: [], data, available_points: []
    } as AfmDetailPayload
  }))
)

test('relationSamples pairs two columns of the same row, tagged with its measurement and point', () => {
  const entries = entriesOf({
    f1: [row('0001', { [L]: 1, [R]: 2 }), row('0002', { [L]: '2', [R]: '4' })],
    f2: [row('0001', { [L]: 3, [R]: 5 })]
  })
  assert.deepEqual(relationSamples(entries, 'A', L, R).samples, [
    { key: 'f1', point: '0001', x: 1, y: 2 },
    { key: 'f1', point: '0002', x: 2, y: 4 },
    { key: 'f2', point: '0001', x: 3, y: 5 }
  ])
})

test('relationSamples leaves out rows that are not COMPLETED or are Valid FALSE, and counts them', () => {
  const entries = entriesOf({
    f1: [
      row('0001', { [L]: 1, [R]: 2 }),
      row('0002', { [L]: 2, [R]: 4 }, { State: 'FAILED' }),
      row('0003', { [L]: 3, [R]: 5 }, { Valid: false }),
      row('0004', {}, { State: 'STOPPED' }),
      // Valid not stated: kept, and counted as unknown.
      row('0005', { [L]: 4, [R]: 9 }, { Valid: null }),
      // Usable, but one axis has no number.
      row('0006', { [L]: 5 }),
      // Another block is not this relation's.
      row('0007', { [L]: 6, [R]: 7 }, { Site: 'B' })
    ]
  })
  assert.deepEqual(relationSamples(entries, 'A', L, R), {
    samples: [{ key: 'f1', point: '0001', x: 1, y: 2 }, { key: 'f1', point: '0005', x: 4, y: 9 }],
    excluded: 3,
    unpaired: 1,
    unknownValid: 1
  })
})

test('relationSamples keeps every lap of a repeat recipe as its own sample', () => {
  const entries = entriesOf({ f1: [row('0001', { [L]: 1, [R]: 2 }), row('0001', { [L]: 3, [R]: 5 })] })
  assert.deepEqual(relationSamples(entries, 'A', L, R).samples.map(s => [s.x, s.y]), [[1, 2], [3, 5]])
})

const pairs = (xs: number[], ys: number[]) => xs.map((x, i) => ({ key: 'f1', point: String(i), x, y: ys[i]! }))
const near = (actual: number | null | undefined, expected: number) =>
  assert.ok(actual != null && Math.abs(actual - expected) < 1e-4, `${actual} is not ${expected}`)

// x = 1 2 3 4, y = 2 4 5 9. Means 2.5 and 5; Sxy = 4.5 + 0.5 + 0 + 6 = 11,
// Sxx = 5, Syy = 9 + 1 + 0 + 16 = 26, so r = 11 / sqrt(130) = 0.9648.
test('relationSummary gives n and Pearson r', () => {
  const summary = relationSummary(pairs([1, 2, 3, 4], [2, 4, 5, 9]))
  assert.equal(summary.n, 4)
  near(summary.r, 0.9648)
})

test('relationSummary gives no statistic under three samples, and no r on a constant axis', () => {
  assert.deepEqual(relationSummary(pairs([1, 2], [2, 4])), { n: 2, r: null })
  assert.deepEqual(relationSummary(pairs([1, 2, 3], [5, 5, 5])), { n: 3, r: null })
})

test('relationColumns offers the block\'s numeric measured columns, and the tip-usage columns it has', () => {
  const entries = entriesOf({
    f1: [row('0001', { '10_Min (nm)': 1, '2_Min (nm)': '3', 'Empty (nm)': ' ', 'Mileage': 120, 'Site X': 2 })],
    f2: [row('0001', { 'Other (nm)': 5, 'Approach Count': 1 }, { Site: 'B' })]
  })
  assert.deepEqual(relationColumns(entries, 'A'), { measured: ['2_Min (nm)', '10_Min (nm)'], usage: ['Mileage'] })
  assert.deepEqual(relationColumns(entries, 'B'), { measured: ['Other (nm)'], usage: ['Approach Count'] })
})

test('relationState: nothing to pair, too few pairs, or a chart', () => {
  // No measured column leaves Y empty; a single column leaves X empty.
  assert.equal(relationState('Mileage', '', 0), 'empty')
  assert.equal(relationState('', L, 0), 'empty')
  assert.equal(relationState(L, R, 0), 'few')
  assert.equal(relationState(L, R, 2), 'few')
  assert.equal(relationState(L, R, 3), 'chart')
})
