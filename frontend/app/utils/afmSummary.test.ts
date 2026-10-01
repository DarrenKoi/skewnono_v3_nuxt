// Pure-logic tests for afmSummary. Run: node --test app/utils/afmSummary.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { summaryColumns, summaryNumber } from './afmSummary.ts'

test('summaryColumns unions ragged rows, drops the id columns, survives an empty summary', () => {
  assert.deepEqual(summaryColumns([{ 'Site': '1', 'ITEM': 'MEAN', 'Left_H (nm)': 1, 'Ref_H (nm)': 2 }]), ['Left_H (nm)', 'Ref_H (nm)'])
  assert.deepEqual(summaryColumns([{ Site: '1', A: 1 }, { Site: '2', A: 1, B: 2 }]), ['A', 'B'])
  assert.deepEqual(summaryColumns([]), [])
})

test('summaryNumber reads numbers and numeric strings, and nothing else', () => {
  assert.equal(summaryNumber(1.5), 1.5)
  assert.equal(summaryNumber('1.5'), 1.5)
  assert.equal(summaryNumber(0), 0)
  for (const bad of ['', '  ', 'n/a', null, undefined, Number.NaN, true]) {
    assert.equal(summaryNumber(bad), null)
  }
})
