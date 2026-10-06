// Run: node --test app/utils/afmInfo.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { infoSlot, tipWidthOf } from './afmInfo.ts'

test('tipWidthOf: the leading number, null for NaN / blank / missing', () => {
  assert.deepEqual(
    ['40.9', '41.2 nm', 'NaN', '', null].map(v => tipWidthOf({ 'Tip Width': v })),
    [40.9, 41.2, null, null, null]
  )
  assert.equal(tipWidthOf({}), null)
})

test('infoSlot: Sample Location first, then Slot No, else undefined', () => {
  assert.equal(infoSlot({ 'Sample Location': 'Slot 11', 'Slot No': '3' }), '11')
  assert.equal(infoSlot({ 'Slot No': '3' }), '3')
  assert.equal(infoSlot({ 'Sample Location': null }), undefined)
})
