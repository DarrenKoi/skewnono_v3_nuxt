// Per-(toolType, fab) recent recipe-search terms, persisted to localStorage.
// Mirrors useAfmCart's recentSearches slice: useState shares one ref across client-side
// navigation, and a watcher in a detached effect scope persists to localStorage so the
// list survives full reloads. Watchers live for the lifetime of the SPA — bounded by
// the tool×fab combinations the user visits, no disposal needed.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const MAX_RECENT_SEARCHES = 10
const MIN_RECORD_LENGTH = 3

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.recent.${toolType}.${fab || 'ALL'}`

const persistenceScope = effectScope(true)
const persistenceWatchers = new Set<string>()

function readJSON<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return fallback
    return parsed as T
  } catch {
    return fallback
  }
}

// Synchronous: an acknowledged user action (record/remove/clear) must be durable before
// the next event loop tick, otherwise a tab close mid-debounce silently drops the change.
function writeJSON(key: string, value: unknown) {
  if (typeof window === 'undefined') return
  try {
    if (Array.isArray(value) && value.length === 0) {
      window.localStorage.removeItem(key)
    } else {
      window.localStorage.setItem(key, JSON.stringify(value))
    }
  } catch { /* noop */ }
}

export const useRecipeRecentSearches = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`
  const key = storageKey(toolType, fab)

  const recentSearches = useState<string[]>(
    `recipe-search:recent:${scope}`,
    () => readJSON<string[]>(key, [])
  )

  if (!persistenceWatchers.has(scope)) {
    persistenceWatchers.add(scope)
    persistenceScope.run(() => {
      watch(recentSearches, next => writeJSON(key, next), { flush: 'sync' })
    })
  }

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
