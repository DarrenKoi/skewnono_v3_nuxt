// Pure-logic tests for afmPointsTable. Run: node --test app/utils/afmPointsTable.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  derivePointColumns,
  filterPointRows,
  pointsSummary,
  pagePointRows,
  DEFAULT_POINT_COLUMN_KEYS
} from './afmPointsTable.ts'

const rows = [
  { measurement_point: '1_UL', 'Point No': 1, 'X (um)': 10, 'State': 'OK', Valid: true, 'CD (nm)': 5, Mileage: 3 },
  { measurement_point: '1_UL', 'Point No': 2, 'X (um)': 11, 'State': 'NG', Valid: false, 'CD (nm)': 6, Mileage: 4 },
  { measurement_point: '2_UR', 'Point No': 1, 'X (um)': 20, 'State': 'OK', Valid: true, 'CD (nm)': 7, Mileage: 5 }
] as any

test('derivePointColumns: preferred first, then (nm), then others; labels applied', () => {
  const cols = derivePointColumns(rows)
  const keys = cols.map(c => c.key)
  // preferred present ones keep their order and come first
  assert.equal(keys[0], 'measurement_point')
  assert.ok(keys.indexOf('CD (nm)') > keys.indexOf('State'))       // nm after preferred
  assert.ok(keys.indexOf('Mileage') > keys.indexOf('CD (nm)'))     // others after nm
  const labelOf = (k: string) => cols.find(c => c.key === k)!.label
  assert.equal(labelOf('measurement_point'), 'Site')
  assert.equal(labelOf('X (um)'), 'X (μm)')
  assert.equal(labelOf('Mileage'), 'Mileage')                       // title-cased unknown
})

test('filterPointRows: point filter only', () => {
  assert.equal(filterPointRows(rows, '1_UL', '', DEFAULT_POINT_COLUMN_KEYS).length, 2)
  assert.equal(filterPointRows(rows, '', '', DEFAULT_POINT_COLUMN_KEYS).length, 3)
})

test('filterPointRows: search is case-insensitive over visible columns only', () => {
  // 'ng' matches State on row 2
  assert.equal(filterPointRows(rows, '', 'ng', ['State']).length, 1)
  // searching a value that lives only in a HIDDEN column returns nothing
  assert.equal(filterPointRows(rows, '', '3', ['State']).length, 0)     // Mileage 3 hidden
  assert.equal(filterPointRows(rows, '', '3', ['Mileage']).length, 1)   // Mileage visible
})

test('filterPointRows: point + search combined', () => {
  assert.equal(filterPointRows(rows, '1_UL', 'ok', ['State']).length, 1)
})

test('pointsSummary: total and valid', () => {
  assert.deepEqual(pointsSummary(rows), { total: 3, valid: 2 })
  assert.deepEqual(pointsSummary([]), { total: 0, valid: 0 })
})

test('pagePointRows: slices and clamps', () => {
  const many = Array.from({ length: 60 }, (_, i) => ({ n: i })) as any
  assert.equal(pagePointRows(many, 1, 25).length, 25)
  assert.equal(pagePointRows(many, 3, 25).length, 10)   // last partial page
  assert.equal(pagePointRows(many, 99, 25).length, 10)  // clamped to last page
  assert.equal(pagePointRows([], 1, 25).length, 0)
})
