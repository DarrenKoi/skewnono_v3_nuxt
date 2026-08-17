// Pure: the shape of the skewvoir 검색 filter set, its predicates, and how it
// is encoded into localStorage.
//
// WHAT CROSSES A RELOAD, AND WHAT DOES NOT
//
// Only the four dropdown picks (FAB / 카테고리 / 장비 모델 / EQ) persist. They
// are a standing description of the fleet a user works on, so re-picking them
// every morning is pure friction.
//
// The date range deliberately stays session-only even though it lives in the
// same object. `from`/`to` hold ABSOLUTE ISO dates that were resolved against
// the backend's declared retention anchor, not wall clock — so a window saved
// today can sit wholly outside retention by the next visit, and restoring it
// would greet the user with a legitimately empty table under an
// out_of_retention banner they never asked for. Left empty, the composable
// falls back to `defaultRange` (anchor − retentionDays … anchor), which is
// correct whenever the page happens to load. The typed query is likewise
// session-only: it is a question, not a setting.
//
// Both directions of the boundary drop the dates — `serialize` so we never
// write them, `normalize` so a key left by an older build (or hand-edited)
// cannot resurrect one.

import type { MeasHistFilters } from '~/composables/useMeasHistSearch'
// Import-free util, so it does not break this module's node:test-runnability.
import { SKEWVOIR_CATEGORIES } from './measHistCascade.ts'

export const emptyMeasHistFilters = (): MeasHistFilters => ({
  fab: [],
  category: [],
  model: [],
  eq: [],
  from: '',
  to: ''
})

const stringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string') : []

/** Storage payload → filters. Anything unreadable degrades to that field being
 *  empty rather than throwing, so one corrupted key never costs the whole set. */
export const normalizeStoredMeasHistFilters = (parsed: unknown): MeasHistFilters => {
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return emptyMeasHistFilters()
  }
  const raw = parsed as Record<string, unknown>
  return {
    fab: stringArray(raw.fab),
    // A category outside the known two would scope the request to no index at
    // all; the value set is closed, so validate it here the way
    // useLiveAlarmFilter validates its mode.
    category: stringArray(raw.category)
      .filter(value => (SKEWVOIR_CATEGORIES as readonly string[]).includes(value)),
    model: stringArray(raw.model),
    eq: stringArray(raw.eq),
    from: '',
    to: ''
  }
}

/** Filters → storage payload: picks only (see the header comment). */
export const serializeMeasHistFilters = (filters: MeasHistFilters): string =>
  JSON.stringify({
    fab: filters.fab,
    category: filters.category,
    model: filters.model,
    eq: filters.eq
  })

/** No picks → drop the storage key rather than writing an all-empty object.
 *  Judged on the picks alone, since the dates are never written anyway. */
export const hasNoMeasHistPicks = (filters: MeasHistFilters): boolean =>
  filters.fab.length === 0
  && filters.category.length === 0
  && filters.model.length === 0
  && filters.eq.length === 0

/** Is anything narrowing the search — a pick or a date window? Drives the
 *  초기화 button and the composable's `hasActiveFilters`. */
export const hasAnyMeasHistFilter = (filters: MeasHistFilters): boolean =>
  !hasNoMeasHistPicks(filters) || Boolean(filters.from) || Boolean(filters.to)
