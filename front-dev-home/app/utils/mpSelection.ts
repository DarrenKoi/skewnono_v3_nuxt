// Pure helpers for Measurement-Points multi-selection. Kept out of the
// composable so they can be unit-tested under `node --test`. Selection is keyed
// by a composite (parameter, sequence) string so the same sequence number under
// two different parameters (multi-param compare) never collides. Keys are only
// ever built and compared via siteKey(), never parsed back, so the separator
// choice is not load-bearing.

/** Composite selection key for one measurement site. */
export function siteKey(param: string, seq: number): string {
  return `${param} ${seq}`
}

/** Toggle `key` in a selection list, returning a new array. */
export function toggleKey(list: string[], key: string): string[] {
  return list.includes(key) ? list.filter(k => k !== key) : [...list, key]
}

/**
 * Tri-state for a select-all header checkbox, computed over the VISIBLE rows
 * only: 'none' (nothing visible selected), 'some' (partial -> indeterminate),
 * 'all' (every visible row selected). An empty visible set is 'none'.
 */
export function headerState(
  visibleKeys: string[],
  selected: ReadonlySet<string>
): 'none' | 'some' | 'all' {
  if (visibleKeys.length === 0) return 'none'
  let hit = 0
  for (const k of visibleKeys) if (selected.has(k)) hit++
  if (hit === 0) return 'none'
  return hit === visibleKeys.length ? 'all' : 'some'
}

/** Export target: all rows when nothing is selected, else checked ∩ visible. */
export function pickExportRows<T>(
  rows: T[],
  selected: ReadonlySet<string>,
  keyOf: (row: T) => string
): T[] {
  if (selected.size === 0) return rows
  return rows.filter(r => selected.has(keyOf(r)))
}
