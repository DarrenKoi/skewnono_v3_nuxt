import type { MeasHistRow } from '~/composables/useMeasHistApi'

// Pure selection helpers keep the working set independent from whichever
// search result page happens to be visible. MSR is the stable measurement key.

// Whether the row has a usable msr key at all. '' is what the office
// adapter's _text() emits when the document carries no msr field
// (OFFICE-VERIFY 2026-08-19, docs/datatables/hitachi/meas_hist.txt) -- everything
// that treats msr as a v-for/dedup key must ask this first.
//
// This is ALSO the whole test for "can this row be opened in analysis", and
// msr_check deliberately plays no part in it. Gating on msr_check went in on
// 2026-08-19 and blanked the office's entire 검색 결과 table: the adapter maps
// every unrecognized value to "No" (providers/office_example.py --
// `_text(...).lower() == "yes"`, so "Y" and a boolean True both become "No"),
// which makes "the office wrote something we did not expect" indistinguishable
// from "this row has no data". Fail-closed is the wrong default here, because
// the two errors are not the same size: a row wrongly blocked is data the user
// cannot reach at all, while a row wrongly opened just renders an empty
// analysis screen. Anything cheap enough to guard belongs in that screen.
export const hasMsrIdentity = (row: MeasHistRow): boolean => row.msr.trim() !== ''

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
  if (!hasMsrIdentity(row)) return selected

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
