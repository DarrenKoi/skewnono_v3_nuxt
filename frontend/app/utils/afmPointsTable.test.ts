// Pure-logic tests for afmPointsTable. Run: node --test app/utils/afmPointsTable.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import {
  derivePointColumns,
  filterPointRows,
  pointsSummary,
  pagePointRows,
  defaultPointColumnKeys,
  facetCounts
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
  'measurement_point': '0001_X000_Y000',
  'Site ID': '0001_X000_Y000',
  'Site X': 0,
  'Site Y': 0,
  'Point No': 1,
  'X (um)': 10,
  'Y (um)': 12,
  'Method_ID': 'Profile_LEFT_UL',
  'State': 'COMPLETED',
  'Valid': true,
  'Pad_1_H (nm)': 88.4,
  'Pad_1_H_Valid': true,
  'Pad_2_H (nm)': 86.1,
  'Pad_2_H_Valid': true,
  'Pick Up Count': 2,
  'Sample Count': 1,
  'Approach Count': 1,
  'Mileage': 3,
  ...overrides
})

const rows: AfmDetailRow[] = [
  row({ 'measurement_point': '0001_X000_Y000', 'Point No': 1, 'X (um)': 10, 'State': 'COMPLETED', 'Valid': true, 'CD (nm)': 5, 'Mileage': 3 }),
  row({ 'measurement_point': '0001_X000_Y000', 'Point No': 2, 'X (um)': 11, 'State': 'FAILED', 'Valid': false, 'CD (nm)': 6, 'Mileage': 4 }),
  row({ 'measurement_point': '0002_X002_Y-001', 'Point No': 1, 'X (um)': 20, 'State': 'COMPLETED', 'Valid': true, 'CD (nm)': 7, 'Mileage': 5 })
]

test('derivePointColumns: ids first, then (nm), then others; labels applied', () => {
  const cols = derivePointColumns(rows)
  const keys = cols.map(c => c.key)
  assert.deepEqual(keys.slice(0, 4), ['measurement_point', 'Point No', 'X (um)', 'Y (um)'])
  // every (nm) column follows the ids, whatever the recipe named it, in natural order
  assert.deepEqual(keys.slice(4, 7), ['CD (nm)', 'Pad_1_H (nm)', 'Pad_2_H (nm)'])
  assert.ok(keys.indexOf('Mileage') > keys.indexOf('Pad_2_H (nm)')) // others after nm
  const labelOf = (k: string) => cols.find(c => c.key === k)!.label
  assert.equal(labelOf('measurement_point'), 'Site')
  assert.equal(labelOf('X (um)'), 'X (μm)')
  assert.equal(labelOf('Pad_1_H (nm)'), 'Pad_1_H') // unit dropped, name verbatim
  assert.equal(labelOf('Mileage'), 'Mileage') // title-cased unknown
})

test('defaultPointColumnKeys: ids, the first six (nm) columns, then State', () => {
  const wide = [row(Object.fromEntries(Array.from({ length: 51 }, (_, i) => [`${i + 1}_Minimum (nm)`, i])))]
  const keys = defaultPointColumnKeys(derivePointColumns(wide))
  assert.deepEqual(keys, [
    'measurement_point', 'Point No', 'X (um)', 'Y (um)',
    '1_Minimum (nm)', '2_Minimum (nm)', '3_Minimum (nm)', '4_Minimum (nm)', '5_Minimum (nm)', '6_Minimum (nm)',
    'State'
  ])
  assert.deepEqual(defaultPointColumnKeys([]), [])
})

test('filterPointRows: point filter only', () => {
  assert.equal(filterPointRows(rows, '0001_X000_Y000', '', ['State']).length, 2)
  assert.equal(filterPointRows(rows, '', '', ['State']).length, 3)
})

test('filterPointRows: search is case-insensitive over visible columns only', () => {
  // 'failed' matches State on row 2
  assert.equal(filterPointRows(rows, '', 'failed', ['State']).length, 1)
  // searching a value that lives only in a HIDDEN column returns nothing
  assert.equal(filterPointRows(rows, '', '3', ['State']).length, 0) // Mileage 3 hidden
  assert.equal(filterPointRows(rows, '', '3', ['Mileage']).length, 1) // Mileage visible
})

test('filterPointRows: point + search combined', () => {
  assert.equal(filterPointRows(rows, '0001_X000_Y000', 'completed', ['State']).length, 1)
})

test('filterPointRows: equals narrows by exact cell text; empty value is no filter', () => {
  assert.equal(filterPointRows(rows, '', '', ['State'], { State: 'FAILED' }).length, 1)
  assert.equal(filterPointRows(rows, '', '', ['State'], { State: '', Valid: 'true' }).length, 2)
  assert.equal(filterPointRows(rows, '0002_X002_Y-001', '', ['State'], { Valid: 'false' }).length, 0)
})

test('facetCounts: counts ignore the facet\'s own filter, keep the others', () => {
  const equals = { State: 'FAILED', Valid: 'true' }
  // State counts: Valid=true still applies, State=FAILED does not.
  assert.deepEqual([...facetCounts(rows, '', '', ['State'], equals, 'State')], [['COMPLETED', 2]])
  // Valid counts: State=FAILED still applies.
  assert.deepEqual([...facetCounts(rows, '', '', ['State'], equals, 'Valid')], [['false', 1]])
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
