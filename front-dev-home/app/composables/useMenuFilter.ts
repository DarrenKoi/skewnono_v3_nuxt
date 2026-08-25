import { filterByTerm } from '~/utils/hardwareCompare'

/**
 * The searchable-and-capped item list behind a scope picker.
 *
 * One sentinel row for "no filter" at the top (a plain '' cannot be a
 * USelectMenu item, and null would render as an empty row rather than as a
 * readable choice), the caller's names filtered by the typed term, and a cap
 * so a pathological list cannot lock the page; `overflowed` is what lets the
 * caption say when the cap bound.
 *
 * The search box keeps its term across openings, so a term typed against the
 * PREVIOUS list would silently filter the new one down to nothing — the menu
 * would read as "there is nothing here". The term is cleared when the list
 * changes identity, so callers must hand a content-stable list (one that only
 * gets a new identity when its contents change).
 */
export const useMenuFilter = (
  names: () => string[],
  { sentinel, limit }: { sentinel: string, limit: number }
) => {
  const term = ref('')
  const matched = computed(() => filterByTerm(names(), term.value, name => name))
  const overflowed = computed(() => matched.value.length > limit)
  // The sentinel stays at the top so clearing the filter is always one click
  // away, even when the search box is narrowing the list down to the cap.
  const items = computed(() => [sentinel, ...matched.value.slice(0, limit)])
  watch(names, () => {
    term.value = ''
  })
  return { term, matched, overflowed, items }
}
