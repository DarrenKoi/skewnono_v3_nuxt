// Pure-logic tests for afmExport. Run: node --test app/utils/afmExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  collectColumns,
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

test('numbered measurement columns come out in natural order, other columns keep their slot', () => {
  // Key order as the API sends it: codepoint-sorted.
  const t = buildDetailedTable([
    { '10_Minimum (nm)': 1, '1_Minimum (nm)': 2, '2_Minimum (nm)': 3, 'Mileage': 4, 'Pad_1_H (nm)': 5 }
  ])
  assert.deepEqual(t.headers, ['1_Minimum (nm)', '2_Minimum (nm)', '10_Minimum (nm)', 'Mileage', 'Pad_1_H (nm)'])
  assert.deepEqual(t.rows[0], [2, 3, 1, 4, 5])
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

test('buildDetailedTable leads with Block so a point measured in two blocks stays two distinguishable rows', () => {
  const t = buildDetailedTable([
    { 'measurement_point': '1', 'Left_H (nm)': 93, 'Block': 'Profile_LEFT_UL' },
    { 'measurement_point': '1', 'Left_H (nm)': 97, 'Block': 'Profile_RIGHT_UL' }
  ])
  assert.deepEqual(t.headers, ['Block', 'measurement_point', 'Left_H (nm)'])
  assert.deepEqual(t.rows, [['Profile_LEFT_UL', '1', 93], ['Profile_RIGHT_UL', '1', 97]])
})

test('buildProfileTable puts the file\'s own units in the headers when it declares them', () => {
  const meta = { x_unit: 'um', y_unit: 'Pixel', z_unit: 'pm', data_size: '2 x 1', surface_size: '1 x 0' }
  const t = buildProfileTable([{ x: 1, y: 2, z: 3 }], meta)
  assert.deepEqual(t.headers, ['x (um)', 'y (Pixel)', 'z (pm)'])
  assert.deepEqual(t.rows, [[1, 2, 3]])
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

test('collectColumns keeps each _Valid column beside its own measurement', () => {
  const keys = ['10_Min (nm)', '10_Min_Valid', '1_Min (nm)', '1_Min_Valid', '2_Min (nm)', '2_Min_Valid']
  assert.deepEqual(
    collectColumns([Object.fromEntries(keys.map(k => [k, 1]))], []),
    ['1_Min (nm)', '1_Min_Valid', '2_Min (nm)', '2_Min_Valid', '10_Min (nm)', '10_Min_Valid']
  )
})
