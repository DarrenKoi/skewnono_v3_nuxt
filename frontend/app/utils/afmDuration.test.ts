// Pure-logic tests for afmDuration. Run: node --test app/utils/afmDuration.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailPayload } from '~/composables/useAfmDetailApi'
import { prepareEntries } from './afmTrend.ts'
import {
  durationByRecipe,
  durationOf,
  durationRows,
  formatDuration,
  formatPerPoint,
  parseInfoTime
} from './afmDuration.ts'

const START = '2026.10.01 00:00:00'
const at = (seconds: number) => {
  const d = new Date(Date.UTC(2026, 9, 1, 0, 0, seconds))
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}.${p(d.getUTCMonth() + 1)}.${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`
}

const entriesOf = (items: { recipe: string, information: Record<string, string | null> }[]) =>
  prepareEntries(items.map(({ recipe, information }, i) => ({
    source: { filename: `f${i}`, recipeName: recipe, lotId: 'LOT1', slotNumber: i + 1, formattedDate: '2026-10-01' },
    payload: {
      filename: `f${i}`, tool: 'MAP608', pickle_filename: 'f.pkl', information, summary: [], data: [], available_points: []
    } as AfmDetailPayload
  })))

const ran = (recipe: string, seconds: number) => ({ recipe, information: { 'Start Time': START, 'End Time': at(seconds) } })

test('parseInfoTime reads the text as KST whatever the machine timezone is', () => {
  assert.equal(parseInfoTime('2026.10.01 00:13:58'), Date.UTC(2026, 8, 30, 15, 13, 58))
})

test('parseInfoTime rejects every other shape', () => {
  for (const bad of [
    '2026-10-01 00:13:58', '2026.10.01 00:13', '2026.02.30 10:00:00', '2026.10.01 24:00:00',
    '2026.10.01 00:60:00', '2026.10.01 00:00:60', '2026.10.01 00:13:58Z', '2026.10.01 00:13:58 KST', '', null, undefined, 5
  ]) assert.equal(parseInfoTime(bad), null, String(bad))
})

test('a run past midnight is plain subtraction', () => {
  assert.deepEqual(
    durationOf({ 'Start Time': '2026.10.01 22:32:28', 'End Time': '2026.10.02 00:11:13' }),
    { kind: 'ok', seconds: 5925 }
  )
})

test('durationOf names why a measurement is not analysed', () => {
  assert.deepEqual(durationOf({}), { kind: 'none', reason: 'no-times' })
  assert.deepEqual(durationOf({ 'Start Time': START }), { kind: 'none', reason: 'no-end' })
  assert.deepEqual(durationOf({ 'End Time': START }), { kind: 'none', reason: 'no-start' })
  assert.deepEqual(durationOf({ 'Start Time': START, 'End Time': 'soon' }), { kind: 'none', reason: 'bad-format' })
  assert.deepEqual(durationOf({ 'Start Time': at(60), 'End Time': START }), { kind: 'none', reason: 'reversed' })
})

test('absent, null and empty values mean the same', () => {
  const missing = { kind: 'none', reason: 'no-end' }
  assert.deepEqual(durationOf({ 'Start Time': START, 'End Time': null }), missing)
  assert.deepEqual(durationOf({ 'Start Time': START, 'End Time': '' }), missing)
  assert.deepEqual(durationOf({ 'Start Time': null, 'End Time': '' }), { kind: 'none', reason: 'no-times' })
})

test('equal times are a zero-second run, not an error', () => {
  assert.deepEqual(durationOf({ 'Start Time': START, 'End Time': START }), { kind: 'ok', seconds: 0 })
})

test('ratio needs 3 durations in the recipe, then is seconds over the median', () => {
  const two = durationRows(entriesOf([ran('A', 100), ran('A', 200)]))
  assert.deepEqual(two.map(row => row.ratio), [null, null])

  const three = durationRows(entriesOf([ran('A', 100), ran('A', 100), ran('A', 200)]))
  assert.deepEqual(three.map(row => row.ratio), [1, 1, 2])
})

test('ratio is null for a zero median and for rows without a duration', () => {
  const rows = durationRows(entriesOf([ran('A', 0), ran('A', 0), ran('A', 0), { recipe: 'A', information: {} }]))
  assert.deepEqual(rows.map(row => row.ratio), [null, null, null, null])
})

test('durationByRecipe counts per recipe in first-appearance order', () => {
  const rows = durationRows(entriesOf([
    ran('A', 100), { recipe: 'B', information: {} }, ran('A', 300), ran('A', 200), { recipe: 'A', information: { 'Start Time': START } }
  ]))
  assert.deepEqual(durationByRecipe(rows), [
    { recipe: 'A', total: 4, counted: 3, median: 200, min: 100, max: 300, medianPerPoint: null },
    { recipe: 'B', total: 1, counted: 0, median: null, min: null, max: null, medianPerPoint: null }
  ])
})

test('formatDuration drops zero units', () => {
  assert.equal(formatDuration(5925), '1시간 38분 45초')
  assert.equal(formatDuration(1564), '26분 4초')
  assert.equal(formatDuration(45), '45초')
  assert.equal(formatDuration(0), '0초')
  assert.equal(formatDuration(3600), '1시간')
})

const row = (point: string, site = 'B1') => ({ measurement_point: point, Site: site, State: 'COMPLETED' })
const measured = (recipe: string, seconds: number, data: object[]) => {
  const [entry] = entriesOf([ran(recipe, seconds)])
  return prepareEntries([{
    source: { filename: entry!.key, recipeName: recipe, lotId: 'LOT1', slotNumber: 1, formattedDate: '2026-10-01' },
    payload: { ...entry!.payload, data } as AfmDetailPayload
  }])[0]!
}

test('seconds per point divide the duration by the data rows of one block', () => {
  const [single] = durationRows([measured('A', 90, [row('0001'), row('0002'), row('0003')])])
  assert.equal(single!.points, 3)
  assert.equal(single!.perPoint, 30)
})

test('a repeat lap is a point measured again, and a second block is not', () => {
  // 2 points x 2 laps in B1; B2 analysed the same 4 readings and stopped after 1.
  const data = [row('0001'), row('0002'), row('0001'), row('0002'), row('0001', 'B2')]
  const [repeat] = durationRows([measured('A', 100, data)])
  assert.equal(repeat!.points, 4)
  assert.equal(repeat!.perPoint, 25)
})

test('no data rows or no duration gives no per-point figure', () => {
  const [noRows] = durationRows([measured('A', 90, [])])
  assert.equal(noRows!.points, 0)
  assert.equal(noRows!.perPoint, null)

  const [entry] = entriesOf([{ recipe: 'A', information: {} }])
  const [noTime] = durationRows([{ ...entry!, rowsByBlock: new Map([['B1', [row('0001')]]]) } as never])
  assert.equal(noTime!.points, 1)
  assert.equal(noTime!.perPoint, null)
})

test('durationByRecipe takes the median of the per-point figures it has', () => {
  const rows = durationRows([
    measured('A', 90, [row('0001'), row('0002'), row('0003')]),
    measured('A', 100, [row('0001'), row('0002')]),
    measured('A', 400, [row('0001')]),
    measured('A', 500, [])
  ])
  assert.equal(durationByRecipe(rows)[0]!.medianPerPoint, 50)
  assert.equal(durationByRecipe(durationRows([measured('B', 500, [])]))[0]!.medianPerPoint, null)
})

test('formatPerPoint keeps a decimal under a minute', () => {
  assert.equal(formatPerPoint(12.34), '12.3초')
  assert.equal(formatPerPoint(0), '0.0초')
  assert.equal(formatPerPoint(164), '2분 44초')
})
