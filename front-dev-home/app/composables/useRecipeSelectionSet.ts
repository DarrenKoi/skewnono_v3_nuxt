// Per-(toolType, fab) persistent recipe working set, persisted via
// usePersistedState so the set survives full reloads. The set powers compare
// (this pass) and, later, a recipe switcher in open/lateral/meas-hist.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.selection.${toolType}.${fab || 'ALL'}`

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`

  const selected = usePersistedState<string[]>(
    `recipe-search:selection:${scope}`,
    storageKey(toolType, fab),
    { default: () => [], normalize: normalizeStringArray }
  )

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
