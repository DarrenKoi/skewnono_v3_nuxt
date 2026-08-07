// Per-toolType recent recipe-search terms, persisted via usePersistedState
// so the list survives full reloads. Search terms are fab-agnostic — a
// recipe-name search typed while browsing one fab is just as useful when
// switching to another, so the list no longer scopes by fab.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const MAX_RECENT_SEARCHES = 10
const MIN_RECORD_LENGTH = 3

const storageKey = (toolType: string) =>
  `skewnono:recipe-search.recent.v2.${toolType}`

export const useRecipeRecentSearches = (toolType: RecipeSearchToolType) => {
  const recentSearches = usePersistedState<string[]>(
    `recipe-search:recent:v2:${toolType}`,
    storageKey(toolType),
    { default: () => [], normalize: normalizeStringArray }
  )

  const recordRecentSearch = (term: string) => {
    const trimmed = term.trim()
    if (trimmed.length < MIN_RECORD_LENGTH) return
    const lower = trimmed.toLowerCase()
    if (recentSearches.value[0]?.toLowerCase() === lower) return
    const next = [
      trimmed,
      ...recentSearches.value.filter(existing => existing.toLowerCase() !== lower)
    ]
    recentSearches.value = next.slice(0, MAX_RECENT_SEARCHES)
  }

  const removeRecentSearch = (term: string) => {
    recentSearches.value = recentSearches.value.filter(existing => existing !== term)
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
