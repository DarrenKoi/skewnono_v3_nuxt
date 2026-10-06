// Pure table builders for the AFM measurement-detail export menu. No DOM/Nuxt
// runtime imports so they run under `node --test`; the page wires these into
// downloadTable / downloadWorkbook from utils/xlsx.
import { toSheetRows } from './tableExport.ts'
import type { WorkbookSheet } from './xlsx.ts'
import type {
  AfmInformation,
  AfmSummaryRow,
  AfmProfileMeta,
  AfmProfilePoint
} from '~/composables/useAfmDetailApi'

// A point id ("1_UL", "Site 3") as a safe piece of a download filename.
export const safeFilePart = (value: string): string =>
  value.replace(/[^a-zA-Z0-9]+/g, '_') || 'point'

export interface ExportTable {
  headers: string[]
  rows: unknown[][]
}

// Measurement columns are named by the recipe (`Pad_1_H (nm)`, `1_Minimum (nm)`, …),
// so they are recognised by their unit, never by name.
export const isMeasurementKey = (key: string) => key.includes('(nm)')

const naturalOrder = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

// Column order = the given leading columns, then every other key in the order
// it first appears across rows. Ragged rows never drop a column.
// The API delivers keys in codepoint order, which puts `10_Minimum (nm)` ahead of
// `1_Minimum (nm)`, so the measurement columns are re-placed in natural order
// among themselves — and so are their `<name>_Valid` columns, or each would sit
// beside another measurement's value. Every other column keeps its slot.
export const collectColumns = (
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
  const isValidKey = (col: string) => col.endsWith('_Valid')
  const renatural = (list: string[], member: (col: string) => boolean) => {
    const sorted = list.filter(member).sort(naturalOrder.compare)
    let next = 0
    return list.map(col => member(col) ? sorted[next++]! : col)
  }
  return renatural(renatural(cols, isMeasurementKey), isValidKey)
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

export const buildSummaryTable = (summary: AfmSummaryRow[]): ExportTable =>
  tableFromRows(summary as unknown as Record<string, unknown>[], ['Site', 'ITEM'])

// Takes any record rows, not AfmDetailRow[]: the job is unioning keys across
// RAGGED rows, and the backend contract is `list[dict[str, Any]]`
// (backend/afm/contracts.py) — the column set varies per recipe.
// `Block` (utils/afmPoints tagBlocks) leads when present: in a multi-block file
// the same point appears once per block, and without it the rows are twins.
export const buildDetailedTable = (data: Record<string, unknown>[]): ExportTable =>
  tableFromRows(data, data.some(row => 'Block' in row) ? ['Block'] : [])

// The headers carry the file's own units: the same numbers mean um in one file and
// Pixel in the next, and a sheet outlives the screen that said which.
export const buildProfileTable = (points: AfmProfilePoint[], meta?: AfmProfileMeta | null): ExportTable => ({
  headers: meta
    ? [`x (${meta.x_unit})`, `y (${meta.y_unit})`, `z (${meta.z_unit})`]
    : ['x', 'y', 'z'],
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
