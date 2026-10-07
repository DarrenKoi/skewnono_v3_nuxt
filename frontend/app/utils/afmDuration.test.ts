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
  assert.deepEqual(durationOf({ 'Start Time': START }), missing)
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
    { recipe: 'A', total: 4, counted: 3, median: 200, min: 100, max: 300 },
    { recipe: 'B', total: 1, counted: 0, median: null, min: null, max: null }
  ])
})

test('formatDuration drops zero units', () => {
  assert.equal(formatDuration(5925), '1시간 38분 45초')
  assert.equal(formatDuration(1564), '26분 4초')
  assert.equal(formatDuration(45), '45초')
  assert.equal(formatDuration(0), '0초')
  assert.equal(formatDuration(3600), '1시간')
})
