// Pure helpers for the AFM measurement-points table (column derivation, filtering). No DOM/Nuxt imports so they run under `node --test`.
import { collectColumns, isMeasurementKey } from './afmExport.ts'
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

export interface PointColumn {
  key: string
  label: string
}

// `Block` exists only on files with more than one block, `Lap` only on a repeat
// measurement (utils/afmPoints tagBlocks / tagLaps).
const ID_COLUMN_KEYS: string[] = ['Block', 'Lap', 'measurement_point', 'Point No', 'X (um)', 'Y (um)']

// A recipe can carry 51 measurement columns; the default view shows the first few.
const DEFAULT_MEASUREMENT_COLUMNS = 6

const LABEL_OVERRIDES: Record<string, string> = {
  'Lap': '회차',
  'measurement_point': 'Site',
  'Point No': '#',
  'X (um)': 'X (μm)',
  'Y (um)': 'Y (μm)'
}

const humanizeKey = (key: string): string =>
  LABEL_OVERRIDES[key] ?? (isMeasurementKey(key)
    ? key.replace(' (nm)', '')
    : key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()))

export const derivePointColumns = (rows: AfmDetailRow[]): PointColumn[] => {
  // `Site` is the row's block name; the table shows it as `Block`, and only
  // where a file has more than one.
  const keys = collectColumns(rows, []).filter(key => key !== 'Site')
  const ids = ID_COLUMN_KEYS.filter(k => keys.includes(k))
  const nm = keys.filter(isMeasurementKey)
  const others = keys.filter(k => !ids.includes(k) && !isMeasurementKey(k))
  return [...ids, ...nm, ...others].map(k => ({ key: k, label: humanizeKey(k) }))
}

export const defaultPointColumnKeys = (columns: PointColumn[]): string[] => {
  const keys = columns.map(c => c.key)
  return [
    ...keys.filter(k => ID_COLUMN_KEYS.includes(k)),
    ...keys.filter(isMeasurementKey).slice(0, DEFAULT_MEASUREMENT_COLUMNS),
    ...keys.filter(k => k === 'State')
  ]
}

// The columns to show for this file out of a pick that is shared by every
// measurement. Measurement columns are named by the recipe, so a pick made on
// one recipe can name none of this file's: it then gets the default ones rather
// than a table of identifiers only. An empty pick is the defaults.
export const resolvePointColumnKeys = (stored: string[], columns: PointColumn[]): string[] => {
  const present = new Set(columns.map(c => c.key))
  const picked = stored.filter(k => present.has(k))
  if (!picked.length) return defaultPointColumnKeys(columns)
  // 회차 arrived after picks were already saved, and without it a repeat
  // measurement's rows are twins — so a pick that predates it still gets it.
  const lap = present.has('Lap') && !picked.includes('Lap') ? ['Lap'] : []
  return picked.some(isMeasurementKey)
    ? [...lap, ...picked]
    : [...lap, ...picked, ...defaultPointColumnKeys(columns).filter(isMeasurementKey)]
}

// A new pick for this file, keeping what was picked for columns it does not
// have — so choosing on one recipe does not erase another recipe's choice.
export const mergePointColumnKeys = (stored: string[], picked: string[], columns: PointColumn[]): string[] => {
  const present = new Set(columns.map(c => c.key))
  return [...stored.filter(k => !present.has(k)), ...picked]
}

export interface PointFilters {
  // '' = every point.
  point?: string
  // Case-insensitive, over the visible columns only; a cell matches by its raw
  // value or by the text the table prints for it (79.236 is shown as 79.24).
  search?: string
  visibleKeys?: string[]
  // Exact cell text per column (`{ State: 'FAILED', Valid: 'false' }`); an
  // empty value means that column is not filtered.
  equals?: Record<string, string>
}

export const filterPointRows = (
  rows: AfmDetailRow[],
  { point = '', search = '', visibleKeys = [], equals = {} }: PointFilters = {}
): AfmDetailRow[] => {
  const wanted = Object.entries(equals).filter(([, value]) => value)
  const q = search.trim().toLowerCase()
  return rows.filter(r =>
    (!point || r.measurement_point === point)
    && wanted.every(([key, value]) => String(r[key]) === value)
    && (!q || visibleKeys.some(k =>
      String(r[k] ?? '').toLowerCase().includes(q) || formatPointCell(r[k]).toLowerCase().includes(q)))
  )
}

// How many rows each value of `key` would leave, with every OTHER filter still
// applied — so a chip's count is what clicking it shows.
export const facetCounts = (rows: AfmDetailRow[], filters: PointFilters, key: string): Map<string, number> => {
  const counts = new Map<string, number>()
  for (const row of filterPointRows(rows, { ...filters, equals: { ...filters.equals, [key]: '' } })) {
    const value = String(row[key])
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }
  return counts
}

// A cell as the table prints it. Unknown is a dash, never FALSE or 0.
export const formatPointCell = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '–'
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  return String(value)
}
