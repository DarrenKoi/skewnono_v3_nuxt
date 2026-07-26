// Single source of truth for "which fab are we looking at when the user has not picked one".
//
// The rule: if no fab is remembered — the store is still at its default, the user cleared the
// selection, or localStorage was empty on first visit — we fall back to R3. Every URL that
// needs a fab segment resolves it through here, so the fallback cannot drift between the
// header, the feature tabs, and the tool-type redirect pages.

// Fab names come from the Flask sem-list response and are uppercase (e.g. "R3", "R4", "M16B").
export const DEFAULT_FAB = 'R3'

// Reserved sentinel for "no fab selected". It is never rendered in the sidebar and must never
// reach a URL — resolveFab() maps it to DEFAULT_FAB.
export const NO_FAB = 'all'

export const hasFab = (fab: string | null | undefined): boolean =>
  !!fab && fab !== NO_FAB

// The remembered fab, or R3 when there is nothing to remember.
export const resolveFab = (fab: string | null | undefined): string =>
  hasFab(fab) ? fab as string : DEFAULT_FAB

// The same value as a URL segment. Fab names are stored uppercase but routed lowercase.
export const fabSegment = (fab: string | null | undefined): string =>
  resolveFab(fab).toLowerCase()
