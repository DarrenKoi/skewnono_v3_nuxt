// Pure helpers for Measurement-Points multi-selection. Kept out of the
// composable so they can be unit-tested under `node --test`.

/** Toggle `seq` in a selection list, returning a new array. */
export function toggleSeq(list: number[], seq: number): number[] {
  return list.includes(seq) ? list.filter(s => s !== seq) : [...list, seq]
}

/**
 * Tri-state for a select-all header checkbox, computed over the VISIBLE rows
 * only: 'none' (nothing visible selected), 'some' (partial → indeterminate),
 * 'all' (every visible row selected). An empty visible set is 'none'.
 */
export function headerState(
  visibleSeqs: number[],
  selected: ReadonlySet<number>
): 'none' | 'some' | 'all' {
  if (visibleSeqs.length === 0) return 'none'
  let hit = 0
  for (const s of visibleSeqs) if (selected.has(s)) hit++
  if (hit === 0) return 'none'
  return hit === visibleSeqs.length ? 'all' : 'some'
}

/** Export target: all rows when nothing is selected, else checked ∩ visible. */
export function pickExportRows<T extends { seq: number }>(
  rows: T[],
  selected: ReadonlySet<number>
): T[] {
  if (selected.size === 0) return rows
  return rows.filter(r => selected.has(r.seq))
}
