// Pure table builders for the AFM measurement-detail export menu. No DOM/Nuxt
// runtime imports so they run under `node --test`; the page wires these into
// downloadTable / downloadWorkbook from utils/xlsx.
import { toSheetRows } from './tableExport.ts'
import type { WorkbookSheet } from './xlsx.ts'
import type {
  AfmInformation,
  AfmSummaryRow,
  AfmProfilePoint
} from '~/composables/useAfmDetailApi'

export interface ExportTable {
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
): ExportTable => {
  const headers = collectColumns(rows, leading)
  const body = rows.map(row => headers.map(col => row[col] ?? ''))
  return { headers, rows: body }
}

export const buildInfoTable = (info: AfmInformation): ExportTable => ({
  headers: ['key', 'value'],
  rows: Object.entries(info).map(([k, v]) => [k, v])
})

export const buildSummaryTable = (summary: AfmSummaryRow[]): ExportTable => {
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
export const buildDetailedTable = (data: Record<string, unknown>[]): ExportTable => {
  if (data.length === 0) return { headers: [], rows: [] }
  return tableFromRows(data, [])
}

export const buildProfileTable = (points: AfmProfilePoint[]): ExportTable => ({
  headers: ['x', 'y', 'z'],
  rows: points.map(p => [p.x, p.y, p.z])
})

export interface ExportSection {
  label: string
  table: ExportTable
}

// 섹션 하나 = 시트 한 장. CSV 시절에는 '## <label>' 줄로 한 파일 안에 섹션을
// 쌓아야 했지만, 그건 형식이 표를 하나밖에 못 담아서 하던 우회였습니다.
// 빈 섹션도 시트로 남기고 '(no data)' 한 줄을 적습니다 — 탭은 있는데 안이
// 비어 있으면 "받다가 잘렸나" 와 구별이 안 됩니다. 시트 이름 정규화(31자·엑셀
// 금지 문자)는 downloadWorkbook 이 safeSheetName 으로 합니다.
export const buildCombinedSheets = (sections: ExportSection[]): WorkbookSheet[] =>
  sections.map(({ label, table }) => ({
    name: label,
    rows: table.rows.length === 0
      ? (table.headers.length ? [table.headers, ['(no data)']] : [['(no data)']])
      : toSheetRows(table.headers, table.rows)
  }))
