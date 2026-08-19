// Pure set-membership helpers for the analysis workspace. Membership is edited
// in ONE place — 세트 편집 in the selection detail modal — and the invariant
// both helpers uphold is that the workspace always keeps an active
// measurement, so the focused MSR can never leave the set. Callers pass the
// result straight to `ws.setMsrs(...)`.
//
// The rail used to carry a second, per-row removal control (a checkbox beside
// each member). It was dropped: it removed the member with no inverse on the
// same screen, and once the set fell to one member the list stopped rendering
// entirely, so a click meant to inspect a measurement could silently end a
// multi-measurement comparison.

/** Empty the set down to just the focused MSR (선택 해제). */
export const clearToFocus = (focusMsr: string): string[] => [focusMsr]

/** Ensure the focused MSR stays in the set. The modal's multi-select set
 *  editor writes the raw selection; this re-adds the focus if the user
 *  deselected it, upholding the "focus is never removable" invariant. */
export const ensureFocus = (list: string[], focusMsr: string): string[] =>
  focusMsr && !list.includes(focusMsr) ? [focusMsr, ...list] : list.slice()
