// Pure-logic tests for afmExport. Run: node --test app/utils/afmExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildInfoTable,
  buildSummaryTable,
  buildDetailedTable,
  buildProfileTable,
  buildCombinedSheets
} from './afmExport.ts'

test('buildInfoTable → key,value rows preserving null', () => {
  const t = buildInfoTable({ 'Recipe ID': 'ABC', 'Lot ID': 'TT01', 'Missing': null })
  assert.deepEqual(t.headers, ['key', 'value'])
  assert.deepEqual(t.rows, [['Recipe ID', 'ABC'], ['Lot ID', 'TT01'], ['Missing', null]])
})

test('buildSummaryTable collects dynamic measurement columns after Site/ITEM', () => {
  const t = buildSummaryTable([
    { 'Site': '1', 'ITEM': 'MEAN', 'CD (nm)': 12, 'H (nm)': 3 },
    { 'Site': '1', 'ITEM': 'STDEV', 'CD (nm)': 0.5, 'H (nm)': 0.1 }
  ])
  assert.deepEqual(t.headers, ['Site', 'ITEM', 'CD (nm)', 'H (nm)'])
  assert.deepEqual(t.rows[0], ['1', 'MEAN', 12, 3])
})

test('buildSummaryTable on empty input → headers only, no rows', () => {
  const t = buildSummaryTable([])
  assert.deepEqual(t.headers, ['Site', 'ITEM'])
  assert.deepEqual(t.rows, [])
})

test('buildDetailedTable unions keys across ragged rows, missing → empty', () => {
  const t = buildDetailedTable([
    { 'Site ID': 'A', 'X (um)': 1 },
    { 'Site ID': 'B', 'X (um)': 2, 'Extra': 9 }
  ])
  assert.deepEqual(t.headers, ['Site ID', 'X (um)', 'Extra'])
  assert.deepEqual(t.rows[0], ['A', 1, ''])
  assert.deepEqual(t.rows[1], ['B', 2, 9])
})

test('buildProfileTable → x,y,z', () => {
  const t = buildProfileTable([{ x: 1, y: 2, z: 3 }])
  assert.deepEqual(t.headers, ['x', 'y', 'z'])
  assert.deepEqual(t.rows, [[1, 2, 3]])
})

// 섹션 하나 = 시트 한 장. 빈 섹션도 시트로 남고 '(no data)' 를 적습니다 —
// 시트가 통째로 없으면 "받다가 잘렸나" 와 구별이 안 됩니다.
test('buildCombinedSheets 는 섹션마다 시트를 내고 빈 섹션도 남긴다', () => {
  const sheets = buildCombinedSheets([
    { label: 'Measurement Info', table: buildInfoTable({ A: '1' }) },
    { label: 'Profile (selected point)', table: buildProfileTable([]) }
  ])
  assert.deepEqual(sheets, [
    { name: 'Measurement Info', rows: [['key', 'value'], ['A', '1']] },
    { name: 'Profile (selected point)', rows: [['x', 'y', 'z'], ['(no data)']] }
  ])
})

test('buildCombinedSheets 는 헤더조차 없는 섹션도 (no data) 한 줄로 낸다', () => {
  const sheets = buildCombinedSheets([
    { label: 'Detailed Points', table: buildDetailedTable([]) }
  ])
  assert.deepEqual(sheets, [{ name: 'Detailed Points', rows: [['(no data)']] }])
})
