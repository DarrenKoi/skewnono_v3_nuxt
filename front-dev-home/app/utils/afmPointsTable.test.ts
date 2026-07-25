// Pure-logic tests for afmPointsTable. Run: node --test app/utils/afmPointsTable.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import {
  derivePointColumns,
  filterPointRows,
  pointsSummary,
  pagePointRows,
  DEFAULT_POINT_COLUMN_KEYS
} from './afmPointsTable.ts'

// Full AfmDetailRow rows, not partials: this fixture is the one place that
// pins the AFM detail row shape, so dropping or renaming a backend field
// breaks the typecheck here. (An *added* field would not — AfmDetailRow ends
// in an `[extra: string]` index signature, which absorbs new keys silently.)
// `overrides` is Partial only in its role as a patch — every row the factory
// returns is complete. Key order matters: derivePointColumns orders
// unrecognised columns by first appearance, so the extra 'CD (nm)' supplied
// via overrides lands after the base keys.
const row = (overrides: Partial<AfmDetailRow>): AfmDetailRow => ({
  'measurement_point': '1_UL',
  'Site ID': '1_UL',
  'Site X': -30000,
  'Site Y': 15000,
  'Point No': 1,
  'X (um)': 10,
  'Y (um)': 12,
  'Method ID': 1,
  'State': 'OK',
  'Valid': true,
  'Left_H (nm)': 88.4,
  'Left_H_Valid': true,
  'Right_H (nm)': 86.1,
  'Right_H_Valid': true,
  'Ref_H (nm)': 79.7,
  'Ref_H_Valid': true,
  'Pick Up Count': 2,
  'Sample Count': 1,
  'Approach Count': 1,
  'Mileage': 3,
  ...overrides
})

const rows: AfmDetailRow[] = [
  row({ 'measurement_point': '1_UL', 'Point No': 1, 'X (um)': 10, 'State': 'OK', 'Valid': true, 'CD (nm)': 5, 'Mileage': 3 }),
  row({ 'measurement_point': '1_UL', 'Point No': 2, 'X (um)': 11, 'State': 'NG', 'Valid': false, 'CD (nm)': 6, 'Mileage': 4 }),
  row({ 'measurement_point': '2_UR', 'Point No': 1, 'X (um)': 20, 'State': 'OK', 'Valid': true, 'CD (nm)': 7, 'Mileage': 5 })
]

test('derivePointColumns: preferred first, then (nm), then others; labels applied', () => {
  const cols = derivePointColumns(rows)
  const keys = cols.map(c => c.key)
  // preferred present ones keep their order and come first
  assert.equal(keys[0], 'measurement_point')
  assert.ok(keys.indexOf('CD (nm)') > keys.indexOf('State')) // nm after preferred
  assert.ok(keys.indexOf('Mileage') > keys.indexOf('CD (nm)')) // others after nm
  const labelOf = (k: string) => cols.find(c => c.key === k)!.label
  assert.equal(labelOf('measurement_point'), 'Site')
  assert.equal(labelOf('X (um)'), 'X (μm)')
  assert.equal(labelOf('Mileage'), 'Mileage') // title-cased unknown
})

test('filterPointRows: point filter only', () => {
  assert.equal(filterPointRows(rows, '1_UL', '', DEFAULT_POINT_COLUMN_KEYS).length, 2)
  assert.equal(filterPointRows(rows, '', '', DEFAULT_POINT_COLUMN_KEYS).length, 3)
})

test('filterPointRows: search is case-insensitive over visible columns only', () => {
  // 'ng' matches State on row 2
  assert.equal(filterPointRows(rows, '', 'ng', ['State']).length, 1)
  // searching a value that lives only in a HIDDEN column returns nothing
  assert.equal(filterPointRows(rows, '', '3', ['State']).length, 0) // Mileage 3 hidden
  assert.equal(filterPointRows(rows, '', '3', ['Mileage']).length, 1) // Mileage visible
})

test('filterPointRows: point + search combined', () => {
  assert.equal(filterPointRows(rows, '1_UL', 'ok', ['State']).length, 1)
})

test('pointsSummary: total and valid', () => {
  assert.deepEqual(pointsSummary(rows), { total: 3, valid: 2 })
  assert.deepEqual(pointsSummary([]), { total: 0, valid: 0 })
})

test('pagePointRows: slices and clamps', () => {
  const many: AfmDetailRow[] = Array.from({ length: 60 }, (_, i) => row({ 'Point No': i }))
  assert.equal(pagePointRows(many, 1, 25).length, 25)
  assert.equal(pagePointRows(many, 3, 25).length, 10) // last partial page
  assert.equal(pagePointRows(many, 99, 25).length, 10) // clamped to last page
  assert.equal(pagePointRows([], 1, 25).length, 0)
})
