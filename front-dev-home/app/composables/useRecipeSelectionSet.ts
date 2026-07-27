// Per-(toolType, fab) persistent recipe working set, persisted via
// usePersistedState so the set survives full reloads. The set powers compare
// (this pass) and, later, a recipe switcher in open/lateral/meas-hist.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import {
  capabilitiesForRecipeSelection,
  normalizeRecipeSelectionEntries,
  promoteRecipeSelectionsToRedis,
  removeRecipeSelection,
  upsertRecipeSelection,
  type RecipeSearchSource,
  type RecipeSelectionEntry
} from '~/utils/recipeSelection'

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.selection.${toolType}.${fab || 'ALL'}`

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`

  const entries = usePersistedState<RecipeSelectionEntry[]>(
    `recipe-search:selection:${scope}`,
    storageKey(toolType, fab),
    { default: () => [], normalize: normalizeRecipeSelectionEntries }
  )

  const selected = computed(() => entries.value.map(entry => entry.name))
  const capabilities = computed(() => capabilitiesForRecipeSelection(entries.value))
  const has = (name: string) => entries.value.some(entry => entry.name === name)
  const sourceOf = (name: string): RecipeSearchSource =>
    entries.value.find(entry => entry.name === name)?.source ?? 'redis'

  const add = (name: string, source: RecipeSearchSource = 'redis') => {
    entries.value = upsertRecipeSelection(entries.value, name, source)
  }

  const remove = (name: string) => {
    entries.value = removeRecipeSelection(entries.value, name)
  }

  const toggle = (name: string, source: RecipeSearchSource = 'redis') => {
    if (has(name)) remove(name)
    else add(name, source)
  }

  const clear = () => {
    entries.value = []
  }

  const promoteRedis = (names: string[]) => {
    entries.value = promoteRecipeSelectionsToRedis(entries.value, names)
  }

  const count = computed(() => entries.value.length)

  return {
    entries,
    selected,
    capabilities,
    count,
    has,
    sourceOf,
    add,
    remove,
    toggle,
    clear,
    promoteRedis
  }
}
