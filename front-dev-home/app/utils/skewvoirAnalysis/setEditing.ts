// Pure set-membership helpers for the CURRENT SELECTION rail. The rail shows
// the compared set's members; unchecking a row removes it, but the focused MSR
// is never removable (the workspace must always keep an active measurement).
// Callers pass the result straight to `ws.setMsrs(...)`.

/** Remove `msr` from the set, unless it is the focused MSR (guarded). */
export const removeFromSet = (list: string[], msr: string, focusMsr: string): string[] => {
  if (msr === focusMsr) return list.slice()
  return list.filter(m => m !== msr)
}

/** Empty the set down to just the focused MSR (선택 해제). */
export const clearToFocus = (focusMsr: string): string[] => [focusMsr]

/** Ensure the focused MSR stays in the set. The modal's multi-select set
 *  editor writes the raw selection; this re-adds the focus if the user
 *  deselected it, upholding the "focus is never removable" invariant. */
export const ensureFocus = (list: string[], focusMsr: string): string[] =>
  focusMsr && !list.includes(focusMsr) ? [focusMsr, ...list] : list.slice()
