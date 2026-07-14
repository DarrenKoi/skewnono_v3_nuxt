// The ONE place we say what counts as a MEASURED row.
//
// "Measured", not "valid": an mp_number < 0 row is not malformed — it is a
// perfectly well-formed row that carries point metadata but no point data, so
// the backend reports cd_value: null (docs/datatables/msr_file_pickle.txt).
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

// Measured CD values for one parameter, in row order.
export const paramValues = (rows: MsrFileRow[], parameter: string): number[] => {
  const out: number[] = []
  for (const row of rows) {
    if (row.parameter === parameter && isMeasuredRow(row)) out.push(row.cd_value)
  }
  return out
}
