// The general set-membership editor is 세트 편집 in the selection detail modal,
// a multi-select the user writes freely. This upholds the one invariant that
// selection cannot express: the workspace always keeps an active measurement,
// so the focused MSR can never leave the set. The caller passes the result
// straight to `ws.setMsrs(...)`.

/** Ensure the focused MSR stays in the set. The modal's multi-select set
 *  editor writes the raw selection; this re-adds the focus if the user
 *  deselected it, upholding the "focus is never removable" invariant. */
export const ensureFocus = (list: string[], focusMsr: string): string[] =>
  focusMsr && !list.includes(focusMsr) ? [focusMsr, ...list] : list.slice()
