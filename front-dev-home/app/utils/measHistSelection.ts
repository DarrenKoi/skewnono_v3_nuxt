import type { MeasHistRow } from '~/composables/useMeasHistApi'

// Pure selection helpers keep the working set independent from whichever
// search result page happens to be visible. MSR is the stable measurement key.

// Whether the row has a usable msr key at all. '' is what the office
// adapter's _text() emits when the document carries no msr field
// (OFFICE-VERIFY 2026-08-19, docs/datatables/meas_hist.txt) -- everything
// that treats msr as a v-for/dedup key must ask this first.
export const hasMsrIdentity = (row: MeasHistRow): boolean => row.msr.trim() !== ''

// Whether the row can actually be opened or compared. msr_check "No" means
// the MSR file was never found and is not stored in MinIO (user-confirmed
// 2026-08-19): even a row that DOES carry an msr value has no raw data
// behind it, so selection and analysis entry gate on this, not on
// hasMsrIdentity alone. At home the mock emits msr '' for such rows, so the
// two conditions coincide -- at the office they may not.
export const isAnalyzableMeasHist = (row: MeasHistRow): boolean =>
  hasMsrIdentity(row) && row.msr_check !== 'No'

// v-for key for a search-result row. The msr where one exists; identity-less
// rows fall back to a composite that cannot collide with an msr (no real msr
// starts with "no-msr:") nor with each other (the index disambiguates true
// duplicates). Without this, several '' keys break Vue's keyed patching --
// "Duplicate keys found during update" -- and neighbouring rows mis-render.
export const measHistRowKey = (row: MeasHistRow, index: number): string =>
  hasMsrIdentity(row)
    ? row.msr
    : `no-msr:${row.lot_id}:${row.eqp_id}:${row.timestamp}:${index}`

export const addMeasHistSelection = (
  selected: MeasHistRow[],
  row: MeasHistRow
): MeasHistRow[] => {
  if (!isAnalyzableMeasHist(row)) return selected

  const index = selected.findIndex(existing => existing.msr === row.msr)
  if (index < 0) return [...selected, row]

  return selected.map((existing, itemIndex) => itemIndex === index ? row : existing)
}

export const removeMeasHistSelection = (
  selected: MeasHistRow[],
  msr: string
): MeasHistRow[] => selected.filter(row => row.msr !== msr)

export const toggleMeasHistSelection = (
  selected: MeasHistRow[],
  row: MeasHistRow
): MeasHistRow[] => selected.some(existing => existing.msr === row.msr)
  ? removeMeasHistSelection(selected, row.msr)
  : addMeasHistSelection(selected, row)

export const setMeasHistSelections = (
  selected: MeasHistRow[],
  rows: MeasHistRow[],
  enabled: boolean
): MeasHistRow[] => {
  if (enabled) {
    return rows.reduce(addMeasHistSelection, selected)
  }

  const removed = new Set(rows.map(row => row.msr))
  return selected.filter(row => !removed.has(row.msr))
}
