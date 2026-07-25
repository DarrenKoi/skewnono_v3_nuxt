// Pure CSV builders for the AFM measurement-detail export menu. No DOM/Nuxt
// runtime imports so they run under `node --test`; the page wires these into
// downloadCsv / downloadCsvRaw from utils/csvDownload.
import { buildCsvContent } from './csvDownload.ts'
import type {
  AfmInformation,
  AfmSummaryRow,
  AfmProfilePoint
} from '~/composables/useAfmDetailApi'

export interface CsvTable {
  headers: string[]
  rows: unknown[][]
}

// Column order = the given leading columns, then every other key in the order
// it first appears across rows. Ragged rows never drop a column.
const collectColumns = (
  rows: Record<string, unknown>[],
  leading: string[]
): string[] => {
  const seen = new Set(leading)
  const cols = [...leading]
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!seen.has(key)) {
        seen.add(key)
        cols.push(key)
      }
    }
  }
  return cols
}

const tableFromRows = (
  rows: Record<string, unknown>[],
  leading: string[]
): CsvTable => {
  const headers = collectColumns(rows, leading)
  const body = rows.map(row => headers.map(col => row[col] ?? ''))
  return { headers, rows: body }
}

export const buildInfoCsv = (info: AfmInformation): CsvTable => ({
  headers: ['key', 'value'],
  rows: Object.entries(info).map(([k, v]) => [k, v])
})

export const buildSummaryCsv = (summary: AfmSummaryRow[]): CsvTable => {
  if (summary.length === 0) return { headers: ['Site', 'ITEM'], rows: [] }
  return tableFromRows(summary as unknown as Record<string, unknown>[], ['Site', 'ITEM'])
}

// Takes any record rows, not AfmDetailRow[]: this is a shape-agnostic
// serializer whose whole job is unioning keys across RAGGED rows, and the
// backend contract for the AFM detail payload is `list[dict[str, Any]]`
// (back_dev_home/afm/contracts.py) — the per-recipe column set genuinely
// varies, so two rows of the same response need not carry the same keys.
// AfmDetailRow's 20 required fields describe only what the mock happens to
// emit; the office adapter is still an unimplemented stub, so pinning this
// signature to them would assert a guarantee no backend has ever made.
// Nothing is lost by widening: the backend-shape claim lives on
// AfmDetailPayload.data, the sole caller still passes an AfmDetailRow[]
// through here, and afmPointsTable.test.ts pins the full row shape.
export const buildDetailedCsv = (data: Record<string, unknown>[]): CsvTable => {
  if (data.length === 0) return { headers: [], rows: [] }
  return tableFromRows(data, [])
}

export const buildProfileCsv = (points: AfmProfilePoint[]): CsvTable => ({
  headers: ['x', 'y', 'z'],
  rows: points.map(p => [p.x, p.y, p.z])
})

export interface CsvSection {
  label: string
  table: CsvTable
}

// Stack labelled sections into one CSV string. Each section is prefixed with a
// '## <label>' line; empty tables render '## <label> (no data)' with no rows.
// Sections separated by a blank line. No BOM (downloadCsvRaw adds it).
export const buildCombinedContent = (sections: CsvSection[]): string =>
  sections
    .map(({ label, table }) =>
      table.rows.length === 0
        ? `## ${label} (no data)`
        : `## ${label}\r\n${buildCsvContent(table.headers, table.rows)}`
    )
    .join('\r\n\r\n')
