// Pure-logic tests for afmPointsTable. Run: node --test app/utils/afmPointsTable.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import {
  derivePointColumns,
  filterPointRows,
  defaultPointColumnKeys,
  facetCounts,
  formatPointCell,
  mergePointColumnKeys,
  resolvePointColumnKeys
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
  'Method ID': 'Profile_LEFT_UL',
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
  assert.equal(filterPointRows(rows, { point: '0001_X000_Y000' }).length, 2)
  assert.equal(filterPointRows(rows).length, 3)
})

test('filterPointRows: search is case-insensitive over visible columns only', () => {
  // 'failed' matches State on row 2
  assert.equal(filterPointRows(rows, { search: 'failed', visibleKeys: ['State'] }).length, 1)
  // searching a value that lives only in a HIDDEN column returns nothing
  assert.equal(filterPointRows(rows, { search: '3', visibleKeys: ['State'] }).length, 0) // Mileage 3 hidden
  assert.equal(filterPointRows(rows, { search: '3', visibleKeys: ['Mileage'] }).length, 1) // Mileage visible
})

test('filterPointRows: point + search combined', () => {
  assert.equal(filterPointRows(rows, { point: '0001_X000_Y000', search: 'completed', visibleKeys: ['State'] }).length, 1)
})

test('filterPointRows: equals narrows by exact cell text; empty value is no filter', () => {
  assert.equal(filterPointRows(rows, { equals: { State: 'FAILED' } }).length, 1)
  assert.equal(filterPointRows(rows, { equals: { State: '', Valid: 'true' } }).length, 2)
  assert.equal(filterPointRows(rows, { point: '0002_X002_Y-001', equals: { Valid: 'false' } }).length, 0)
})

test('facetCounts: counts ignore the facet\'s own filter, keep the others', () => {
  const filters = { equals: { State: 'FAILED', Valid: 'true' } }
  // State counts: Valid=true still applies, State=FAILED does not.
  assert.deepEqual([...facetCounts(rows, filters, 'State')], [['COMPLETED', 2]])
  // Valid counts: State=FAILED still applies.
  assert.deepEqual([...facetCounts(rows, filters, 'Valid')], [['false', 1]])
})

test('formatPointCell: an unknown cell is a dash, never FALSE or 0', () => {
  assert.deepEqual(
    [undefined, null, '', true, false, 3, 79.236, 'COMPLETED'].map(formatPointCell),
    ['–', '–', '–', 'TRUE', 'FALSE', '3', '79.24', 'COMPLETED']
  )
})

test('a column pick made on one recipe still shows another recipe its measurements', () => {
  const cols = (nm: string) => ['measurement_point', 'Point No', nm, 'State'].map(key => ({ key, label: key }))
  const left = cols('Left_H (nm)')
  const bottom = cols('Bottom_H (nm)')
  const stored = ['measurement_point', 'Left_H (nm)', 'State']
  assert.deepEqual(resolvePointColumnKeys(stored, left), stored)
  // None of the pick's measurement columns exist here: the defaults join it.
  assert.deepEqual(resolvePointColumnKeys(stored, bottom), ['measurement_point', 'State', 'Bottom_H (nm)'])
  assert.deepEqual(resolvePointColumnKeys([], bottom), defaultPointColumnKeys(bottom))
  // Picking on the other recipe keeps the first recipe's column.
  assert.deepEqual(mergePointColumnKeys(stored, ['Point No', 'Bottom_H (nm)'], bottom), ['Left_H (nm)', 'Point No', 'Bottom_H (nm)'])
})

test('search matches a cell by the text the table prints', () => {
  const data = [row({ 'measurement_point': 'A', 'Left_H (nm)': 12.3456 })]
  const hit = (search: string) => filterPointRows(data, { search, visibleKeys: ['Left_H (nm)'] }).length
  assert.deepEqual([hit('12.35'), hit('12.345'), hit('99')], [1, 1, 0])
})

test('회차 is always shown on a repeat measurement: an old pick gets it, a new pick cannot drop it', () => {
  const columns = derivePointColumns(rows.map((r, i) => ({ ...r, Lap: i + 1 })))
  assert.deepEqual(columns.slice(0, 2).map(c => [c.key, c.label]), [['Lap', '회차'], ['measurement_point', 'Site']])
  assert.ok(defaultPointColumnKeys(columns).includes('Lap'))
  assert.deepEqual(resolvePointColumnKeys(['State', 'Pad_1_H (nm)'], columns), ['Lap', 'State', 'Pad_1_H (nm)'])
  // The picker does not offer it, so a pick never names it — and never loses it.
  assert.deepEqual(resolvePointColumnKeys(mergePointColumnKeys(['Lap', 'State'], ['State', 'Pad_1_H (nm)'], columns), columns).slice(0, 1), ['Lap'])
  // No repeat, no column to add.
  assert.deepEqual(resolvePointColumnKeys(['State', 'Pad_1_H (nm)'], derivePointColumns(rows)), ['State', 'Pad_1_H (nm)'])
})
