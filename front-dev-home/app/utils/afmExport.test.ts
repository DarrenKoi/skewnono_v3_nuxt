// Pure-logic tests for afmExport. Run: node --test app/utils/afmExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildInfoCsv,
  buildSummaryCsv,
  buildDetailedCsv,
  buildProfileCsv,
  buildCombinedContent
} from './afmExport.ts'

test('buildInfoCsv → key,value rows preserving null', () => {
  const t = buildInfoCsv({ 'Recipe ID': 'ABC', 'Lot ID': 'TT01', 'Missing': null })
  assert.deepEqual(t.headers, ['key', 'value'])
  assert.deepEqual(t.rows, [['Recipe ID', 'ABC'], ['Lot ID', 'TT01'], ['Missing', null]])
})

test('buildSummaryCsv collects dynamic measurement columns after Site/ITEM', () => {
  const t = buildSummaryCsv([
    { 'Site': '1', 'ITEM': 'MEAN', 'CD (nm)': 12, 'H (nm)': 3 },
    { 'Site': '1', 'ITEM': 'STDEV', 'CD (nm)': 0.5, 'H (nm)': 0.1 }
  ])
  assert.deepEqual(t.headers, ['Site', 'ITEM', 'CD (nm)', 'H (nm)'])
  assert.deepEqual(t.rows[0], ['1', 'MEAN', 12, 3])
})

test('buildSummaryCsv on empty input → headers only, no rows', () => {
  const t = buildSummaryCsv([])
  assert.deepEqual(t.headers, ['Site', 'ITEM'])
  assert.deepEqual(t.rows, [])
})

test('buildDetailedCsv unions keys across ragged rows, missing → empty', () => {
  const t = buildDetailedCsv([
    { 'Site ID': 'A', 'X (um)': 1 },
    { 'Site ID': 'B', 'X (um)': 2, 'Extra': 9 }
  ])
  assert.deepEqual(t.headers, ['Site ID', 'X (um)', 'Extra'])
  assert.deepEqual(t.rows[0], ['A', 1, ''])
  assert.deepEqual(t.rows[1], ['B', 2, 9])
})

test('buildProfileCsv → x,y,z', () => {
  const t = buildProfileCsv([{ x: 1, y: 2, z: 3 }])
  assert.deepEqual(t.headers, ['x', 'y', 'z'])
  assert.deepEqual(t.rows, [[1, 2, 3]])
})

test('buildCombinedContent labels sections and marks empty ones (no data)', () => {
  const out = buildCombinedContent([
    { label: 'Measurement Info', table: buildInfoCsv({ A: '1' }) },
    { label: 'Profile (selected point)', table: buildProfileCsv([]) }
  ])
  assert.equal(
    out,
    '## Measurement Info\r\n"key","value"\r\n"A","1"\r\n\r\n## Profile (selected point) (no data)'
  )
})
