// Per-(toolType, fab) persistent recipe working set, persisted to localStorage.
// Mirrors useRecipeRecentSearches: useState shares one ref across client-side
// navigation; a watcher in a detached effect scope persists to localStorage so the
// set survives full reloads. The set powers compare (this pass) and, later, a
// recipe switcher in open/lateral/meas-hist.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.selection.${toolType}.${fab || 'ALL'}`

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

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`
  const key = storageKey(toolType, fab)

  const selected = useState<string[]>(
    `recipe-search:selection:${scope}`,
    () => readJSON<string[]>(key, [])
  )

  if (!persistenceWatchers.has(scope)) {
    persistenceWatchers.add(scope)
    persistenceScope.run(() => {
      watch(selected, next => writeJSON(key, next), { flush: 'sync' })
    })
  }

  const has = (name: string) => selected.value.includes(name)

  const add = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed || has(trimmed)) return
    selected.value = [...selected.value, trimmed]
  }

  const remove = (name: string) => {
    selected.value = selected.value.filter(existing => existing !== name)
  }

  const toggle = (name: string) => {
    if (has(name)) remove(name)
    else add(name)
  }

  const clear = () => {
    selected.value = []
  }

  const count = computed(() => selected.value.length)

  return { selected, has, add, remove, toggle, clear, count }
}
