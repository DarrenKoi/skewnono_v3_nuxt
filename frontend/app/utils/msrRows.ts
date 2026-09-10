// The ONE place we say what counts as a MEASURED row.
//
// "Measured", not "valid": an mp_number < 0 row is not malformed — it is a
// perfectly well-formed row that carries point metadata but no point data, so
// the backend reports cd_value: null (docs/datatables/hitachi/msr_file_pickle.txt).
// Nothing is wrong with it; there is simply no measurement in it, and no mean,
// sigma or outlier verdict may be computed from it.
//
// We check BOTH conditions rather than trusting either alone: the null is the
// contract, and the mp_number check is defence in depth for an office backend
// that may not honour it.
//
// isMeasuredRow is a type guard, so MeasuredMsrRow.cd_value is a plain `number` —
// downstream code cannot forget the null, because the compiler removes it.
import type { MsrFileRow } from '~/composables/useMsrFileApi'

export type MeasuredMsrRow = MsrFileRow & { cd_value: number }

export const isMeasuredRow = (row: MsrFileRow): row is MeasuredMsrRow =>
  row.mp_number >= 0 && row.cd_value != null && Number.isFinite(row.cd_value)

export const measuredRows = (rows: MsrFileRow[]): MeasuredMsrRow[] => rows.filter(isMeasuredRow)

// The ONE place we say which image-carrying ROWS belong to a parameter: the
// first measured row per distinct mp_image_name_01, in row order. The gallery
// grid renders these; the cache warmer prefetches exactly the same set —
// sharing the derivation is what keeps "what we warm" and "what we show"
// identical. Consumers expand each row to its FILES via rowImageNames below
// (an HV-SEM row carries several).
export const paramImageRows = (rows: MsrFileRow[], parameter: string): MeasuredMsrRow[] => {
  const seen = new Set<string>()
  const out: MeasuredMsrRow[] = []
  for (const row of rows) {
    if (row.parameter !== parameter || !isMeasuredRow(row)) continue
    const name = row.mp_image_name_01
    if (name && !seen.has(name)) {
      seen.add(name)
      out.push(row)
    }
  }
  return out
}

// The image files of ONE row, in pickle column order. `mp_image_names` is the
// contract since 2026-08-08 (an HV-SEM row carries several stem-suffixed
// files); the `_01` fallback keeps anything that predates the field — a cached
// response, an older office adapter — rendering its single image instead of
// none.
export const rowImageNames = (row: MsrFileRow): string[] => {
  const names = (row.mp_image_names ?? []).filter(name => !!name)
  if (names.length > 0) return names
  return row.mp_image_name_01 ? [row.mp_image_name_01] : []
}

// Measured CD values for one parameter, in row order.
export const paramValues = (rows: MsrFileRow[], parameter: string): number[] => {
  const out: number[] = []
  for (const row of rows) {
    if (row.parameter === parameter && isMeasuredRow(row)) out.push(row.cd_value)
  }
  return out
}
