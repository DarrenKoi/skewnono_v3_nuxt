// Pure-logic tests for afmLotHistory. Run: node --test app/utils/afmLotHistory.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmMeasurement } from '~/composables/useAfmCart'
import { lotHistory, pickForGroup } from './afmLotHistory.ts'

const row = (filename: string, lotId: string, slotNumber: number | string, formattedDate: string, recipeName = 'CMP_POST'): AfmMeasurement => ({
  filename,
  recipeName,
  lotId,
  slotNumber,
  measuredInfo: '',
  formattedDate
})

const names = (rows: AfmMeasurement[]) => rows.map(item => item.filename)

test('lotHistory: the same lot and slot, oldest first, the opened measurement among them', () => {
  const rows = [
    row('c', 'MON69AB', '5', '2026-10-03 09:00:00'),
    row('x', 'MON70ZZ', '5', '2026-10-02 09:00:00'),
    row('a', 'MON69AB', '5', '2026-10-01 09:00:00'),
    row('b', 'MON69AB', '5', '2026-10-02 09:00:00')
  ]
  assert.deepEqual(names(lotHistory(rows, 'b')!.wafer), ['a', 'b', 'c'])
})

test('lotHistory: a slot is the same slot with or without its leading zero, as text or number', () => {
  // The list mixes `5` (from Info) and `07` (from the file name's tail).
  const rows = [
    row('a', 'MON69AB', '07', '2026-10-01 09:00:00'),
    row('b', 'MON69AB', '7', '2026-10-02 09:00:00'),
    row('c', 'MON69AB', 7, '2026-10-03 09:00:00'),
    row('d', 'MON69AB', '17', '2026-10-04 09:00:00')
  ]
  assert.deepEqual(names(lotHistory(rows, 'b')!.wafer), ['a', 'b', 'c'])
})

test('lotHistory: measurements with no lot or no slot are never each other\'s history', () => {
  const rows = [
    row('noSlot1', 'MON69AB', '', '2026-10-01 09:00:00'),
    row('noSlot2', 'MON69AB', '', '2026-10-02 09:00:00'),
    row('noLot1', '', '5', '2026-10-01 09:00:00'),
    row('noLot2', ' ', '5', '2026-10-02 09:00:00')
  ]
  assert.equal(lotHistory(rows, 'noSlot1'), null)
  assert.equal(lotHistory(rows, 'noLot1'), null)
  assert.equal(lotHistory(rows, 'not-in-the-list'), null)
})

test('lotHistory: the lot\'s other slots are listed apart, and its slotless rows only counted', () => {
  const rows = [
    row('s5-late', 'MON69AB', '5', '2026-10-05 09:00:00'),
    row('s9', 'MON69AB', '9', '2026-10-04 09:00:00'),
    row('s2', 'MON69AB', '02', '2026-10-06 09:00:00'),
    row('s5', 'MON69AB', '5', '2026-10-01 09:00:00'),
    row('unknown', 'MON69AB', '', '2026-10-02 09:00:00'),
    row('other-lot', 'MON70ZZ', '9', '2026-10-03 09:00:00')
  ]
  const history = lotHistory(rows, 's5')!
  assert.deepEqual(names(history.wafer), ['s5', 's5-late'])
  assert.deepEqual(names(history.otherSlots), ['s9', 's2'])
  assert.equal(history.noSlot, 1)
})

test('lotHistory: the same moment keeps one order by file name, and an undated row goes last', () => {
  const rows = [
    row('undated', 'MON69AB', '5', ''),
    row('b', 'MON69AB', '5', '2026-10-01 09:00:00'),
    row('a', 'MON69AB', '5', '2026-10-01 09:00:00')
  ]
  assert.deepEqual(names(lotHistory(rows, 'a')!.wafer), ['a', 'b', 'undated'])
})

// Seven measurements of one wafer, a day apart; d4 is the opened one.
const week = [
  row('d1', 'MON69AB', '5', '2026-10-01 09:00:00'),
  row('d2', 'MON69AB', '5', '2026-10-02 09:00:00', 'ETCH_TRIM'),
  row('d3', 'MON69AB', '5', '2026-10-03 09:00:00'),
  row('d4', 'MON69AB', '5', '2026-10-04 09:00:00'),
  row('d5', 'MON69AB', '5', '2026-10-05 09:00:00'),
  row('d6', 'MON69AB', '5', '2026-10-06 09:00:00', 'ETCH_TRIM'),
  row('d7', 'MON69AB', '5', '2026-10-07 09:00:00')
]
const d4 = week[3]!
const none = () => false

test('pickForGroup: the opened recipe only, with the other recipes counted', () => {
  const pick = pickForGroup(week, d4, 20, none, true)
  assert.deepEqual(names(pick.add), ['d1', 'd3', 'd4', 'd5', 'd7'])
  assert.equal(pick.otherRecipe, 2)
  assert.equal(pick.leftOut, 0)
})

test('pickForGroup: every recipe when asked, minus what the group already holds', () => {
  const pick = pickForGroup(week, d4, 20, name => name === 'd4' || name === 'd6', false)
  assert.deepEqual(names(pick.add), ['d1', 'd2', 'd3', 'd5', 'd7'])
  assert.equal(pick.otherRecipe, 2)
  assert.equal(pick.leftOut, 0)
})

test('pickForGroup: past the room, the measurements nearest the opened one stay, and the rest are counted', () => {
  const pick = pickForGroup(week, d4, 3, none, false)
  assert.deepEqual(names(pick.add), ['d3', 'd4', 'd5'])
  assert.equal(pick.leftOut, 4)
  // An even room leans to the earlier side: the history is what came before.
  assert.deepEqual(names(pickForGroup(week, d4, 4, none, false).add), ['d2', 'd3', 'd4', 'd5'])
  // The opened one is already in the group: it still anchors what is nearest.
  assert.deepEqual(names(pickForGroup(week, d4, 2, name => name === 'd4', false).add), ['d3', 'd5'])
})

test('pickForGroup: a full group takes nothing and says how many it refused', () => {
  const pick = pickForGroup(week, d4, 0, none, true)
  assert.deepEqual(pick.add, [])
  assert.equal(pick.leftOut, 5)
})

test('pickForGroup: the lot\'s other slots are ranked around the opened measurement too', () => {
  const lot = [...week, row('s9-early', 'MON69AB', '9', '2026-10-03 12:00:00'), row('s9-late', 'MON69AB', '9', '2026-10-09 09:00:00')]
  assert.deepEqual(names(pickForGroup(lot, d4, 3, none, true).add), ['s9-early', 'd4', 'd5'])
})
