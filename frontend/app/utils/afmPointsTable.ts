// Pure helpers for the AFM measurement-points table (column derivation, filtering,
// summary, paging). No DOM/Nuxt imports so they run under `node --test`.
import { collectColumns } from './afmExport.ts'
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

export interface PointColumn {
  key: string
  label: string
}

// `Block` exists only on files with more than one block (utils/afmPoints tagBlocks).
const ID_COLUMN_KEYS: string[] = ['Block', 'measurement_point', 'Point No', 'X (um)', 'Y (um)']

// Measurement columns are named by the recipe (`Pad_1_H (nm)`, `1_Minimum (nm)`, …),
// so they are recognised by their unit, never by name.
export const isMeasurementKey = (key: string) => key.includes('(nm)')

// A recipe can carry 51 measurement columns; the default view shows the first few.
const DEFAULT_MEASUREMENT_COLUMNS = 6

const LABEL_OVERRIDES: Record<string, string> = {
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
  const keys = collectColumns(rows, [])
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

export interface PointFilters {
  // '' = every point.
  point?: string
  // Case-insensitive, over the visible columns only.
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
    && (!q || visibleKeys.some(k => String(r[k] ?? '').toLowerCase().includes(q)))
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

export interface PointsSummary {
  total: number
  valid: number
}

export const pointsSummary = (rows: AfmDetailRow[]): PointsSummary => ({
  total: rows.length,
  valid: rows.reduce((n, r) => n + (r.Valid === true ? 1 : 0), 0)
})

export const pagePointRows = (
  rows: AfmDetailRow[],
  page: number,
  pageSize: number
): AfmDetailRow[] => {
  if (rows.length === 0 || pageSize <= 0) return []
  const maxPage = Math.max(1, Math.ceil(rows.length / pageSize))
  const p = Math.min(Math.max(1, Math.floor(page) || 1), maxPage)
  const start = (p - 1) * pageSize
  return rows.slice(start, start + pageSize)
}
