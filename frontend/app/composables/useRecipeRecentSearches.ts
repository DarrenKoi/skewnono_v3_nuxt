// Per-toolType recent recipe-search entries, persisted via usePersistedState
// so the list survives full reloads. Each entry carries the fabs it was
// searched in (see utils/recipeRecentSearches) — the v2 list stored bare
// terms, and replaying one under a different fab matched nothing in that
// fab's catalog and fell through to the OpenSearch probe.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import {
  addRecipeRecentSearch,
  normalizeRecipeRecentSearches,
  recipeRecentSearchKey,
  type RecipeRecentSearch
} from '~/utils/recipeRecentSearches'
import { canonicalFabList } from '~/utils/fab'

const MAX_RECENT_SEARCHES = 10
const MIN_RECORD_LENGTH = 3

// v3: entries are {term, fabs}; normalize migrates v2 strings in place.
const storageKey = (toolType: string) =>
  `skewnono:recipe-search.recent.v3.${toolType}`

export const useRecipeRecentSearches = (toolType: RecipeSearchToolType) => {
  const recentSearches = usePersistedState<RecipeRecentSearch[]>(
    `recipe-search:recent:v3:${toolType}`,
    storageKey(toolType),
    { default: () => [], normalize: normalizeRecipeRecentSearches }
  )

  const recordRecentSearch = (term: string, fabs: readonly string[]) => {
    const trimmed = term.trim()
    if (trimmed.length < MIN_RECORD_LENGTH) return
    const entry = { term: trimmed, fabs: canonicalFabList(fabs) }
    if (recentSearches.value[0] && recipeRecentSearchKey(recentSearches.value[0]) === recipeRecentSearchKey(entry)) return
    recentSearches.value = addRecipeRecentSearch(recentSearches.value, entry, MAX_RECENT_SEARCHES)
  }

  const removeRecentSearch = (entry: RecipeRecentSearch) => {
    const key = recipeRecentSearchKey(entry)
    recentSearches.value = recentSearches.value.filter(existing => recipeRecentSearchKey(existing) !== key)
  }

  const clearRecentSearches = () => {
    recentSearches.value = []
  }

  return {
    recentSearches,
    recordRecentSearch,
    removeRecentSearch,
    clearRecentSearches
  }
}
