import type { MeasHistRow } from '~/composables/useMeasHistApi'

// Pure selection helpers keep the working set independent from whichever
// search result page happens to be visible. MSR is the stable measurement key.
export const addMeasHistSelection = (
  selected: MeasHistRow[],
  row: MeasHistRow
): MeasHistRow[] => {
  if (!row.msr.trim()) return selected

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
