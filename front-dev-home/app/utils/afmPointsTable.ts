// Pure helpers for the AFM measurement-points table (column derivation, filtering,
// summary, paging). No DOM/Nuxt imports so they run under `node --test`.
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

export interface PointColumn {
  key: string
  label: string
}

export const DEFAULT_POINT_COLUMN_KEYS: string[] = [
  'measurement_point', 'Point No', 'X (um)', 'Y (um)',
  'Left_H (nm)', 'Right_H (nm)', 'Ref_H (nm)', 'State'
]

const LABEL_OVERRIDES: Record<string, string> = {
  'measurement_point': 'Site',
  'Point No': '#',
  'X (um)': 'X (μm)',
  'Y (um)': 'Y (μm)',
  'Left_H (nm)': 'Left_H',
  'Right_H (nm)': 'Right_H',
  'Ref_H (nm)': 'Ref_H'
}

const humanizeKey = (key: string): string =>
  LABEL_OVERRIDES[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

export const derivePointColumns = (rows: AfmDetailRow[]): PointColumn[] => {
  const seen = new Set<string>()
  const keys: string[] = []
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (!seen.has(k)) {
        seen.add(k)
        keys.push(k)
      }
    }
  }
  const preferred = DEFAULT_POINT_COLUMN_KEYS.filter(k => seen.has(k))
  const rest = keys.filter(k => !DEFAULT_POINT_COLUMN_KEYS.includes(k))
  const nm = rest.filter(k => k.includes('(nm)'))
  const others = rest.filter(k => !k.includes('(nm)'))
  return [...preferred, ...nm, ...others].map(k => ({ key: k, label: humanizeKey(k) }))
}

export const filterPointRows = (
  rows: AfmDetailRow[],
  selectedPoint: string,
  search: string,
  visibleKeys: string[]
): AfmDetailRow[] => {
  let out = selectedPoint
    ? rows.filter(r => r.measurement_point === selectedPoint)
    : rows
  const q = search.trim().toLowerCase()
  if (q) {
    out = out.filter(r =>
      visibleKeys.some(k =>
        String((r as Record<string, unknown>)[k] ?? '').toLowerCase().includes(q)
      )
    )
  }
  return out
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
