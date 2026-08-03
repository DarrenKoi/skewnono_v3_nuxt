// Ordering for the 스큐보아 search result table.
//
// Pure and framework-free so it runs under raw `node --test`; the composable
// only wires it to reactive state and ResultTable.vue only renders the result.
//
// SCOPE: this sorts the rows already LOADED, never the full result set. The
// backend answers a search sorted by timestamp desc and pages it 50 at a time,
// so sorting by RECIPE over a 169-hit search orders the newest 50 — not the 169.
// That limit is real and the table says so out loud (see ResultTable.vue's
// partial-sort notice); it is not hidden behind a header that looks authoritative.

export type MeasHistSortKey = 'timestamp' | 'recipe' | 'eq' | 'lot'
export type MeasHistSortDir = 'asc' | 'desc'

export interface MeasHistSort {
  key: MeasHistSortKey
  dir: MeasHistSortDir
}

/** The backend's own order: newest first. Keeping this as the default means the
 *  table behaves exactly as before until a header is actually clicked. */
export const DEFAULT_MEAS_HIST_SORT: MeasHistSort = { key: 'timestamp', dir: 'desc' }

/** Fields a row must expose to be sortable. Structural rather than MeasHistRow
 *  so tests can build one without a 28-field fixture. */
export interface SortableMeasHistRow {
  msr: string
  full_name: string
  eqp_id: string
  lot_id: string
  timestamp: string
}

const VALUE_OF: Record<MeasHistSortKey, (row: SortableMeasHistRow) => string> = {
  // RECIPE renders full_name (CLASS/RECIPE), so it sorts on what is displayed —
  // sorting recipe_name under a column showing full_name would look broken.
  recipe: row => row.full_name,
  eq: row => row.eqp_id,
  lot: row => row.lot_id,
  // ISO-8601 with a fixed offset, so lexical order IS chronological order.
  timestamp: row => row.timestamp
}

/**
 * Sort a copy of `rows`. Never mutates the input — the caller's array is search
 * session state shared across the SPA, and `loadMore` appends to it.
 *
 * `msr` breaks ties. Without it, two runs of one recipe (a common case, and
 * exactly what a set-building user is looking at) hold an arbitrary relative
 * order that Array.prototype.sort is free to change between renders.
 */
export const sortMeasHistRows = <T extends SortableMeasHistRow>(
  rows: readonly T[],
  { key, dir }: MeasHistSort
): T[] => {
  const value = VALUE_OF[key] ?? VALUE_OF.timestamp
  const sign = dir === 'asc' ? 1 : -1

  return [...rows].sort((a, b) => {
    const compared = value(a).localeCompare(value(b))
    if (compared !== 0) return sign * compared
    return a.msr.localeCompare(b.msr)
  })
}

/**
 * What clicking a header does. First click on a new column starts DESCENDING
 * for time (newest first is what "sort by date" means to anyone reading a
 * measurement log) and ASCENDING for the three text columns (A→Z). Clicking the
 * active column flips it.
 */
export const nextMeasHistSort = (current: MeasHistSort, key: MeasHistSortKey): MeasHistSort => {
  if (current.key === key) {
    return { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
  }
  return { key, dir: key === 'timestamp' ? 'desc' : 'asc' }
}

/** True when the active sort is not the order the backend already returned, so
 *  the rows on screen are a re-ordering of the loaded page rather than of the
 *  whole result set. Drives the partial-sort notice. */
export const isReordered = (sort: MeasHistSort): boolean =>
  sort.key !== DEFAULT_MEAS_HIST_SORT.key || sort.dir !== DEFAULT_MEAS_HIST_SORT.dir
