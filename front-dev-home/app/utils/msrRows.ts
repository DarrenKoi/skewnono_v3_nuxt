// The ONE place the raw-row validity rule is written down.
//
// A row with mp_number < 0 carries point metadata but no point data, so the
// backend reports cd_value: null (docs/datatables/msr_file_pickle.txt). We check
// BOTH conditions rather than trusting either alone: the null is the contract,
// and the mp_number check is defence in depth for an office backend that may not
// honour it.
//
// isValidRow is a type guard, so ValidMsrRow.cd_value is a plain `number` —
// downstream code cannot forget the null, because the compiler removes it.
import type { MsrFileRow } from '~/composables/useMsrFileApi'

export type ValidMsrRow = MsrFileRow & { cd_value: number }

export const isValidRow = (row: MsrFileRow): row is ValidMsrRow =>
  row.mp_number >= 0 && row.cd_value != null && Number.isFinite(row.cd_value)

export const validRows = (rows: MsrFileRow[]): ValidMsrRow[] => rows.filter(isValidRow)

// Measured CD values for one parameter, in row order.
export const paramValues = (rows: MsrFileRow[], parameter: string): number[] => {
  const out: number[] = []
  for (const row of rows) {
    if (row.parameter === parameter && isValidRow(row)) out.push(row.cd_value)
  }
  return out
}
