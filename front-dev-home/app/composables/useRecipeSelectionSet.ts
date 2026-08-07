// Per-toolType persistent recipe working set, persisted via usePersistedState
// so the set survives full reloads. Selection identity is the (name, fab)
// pair — the same recipe name can be selected from more than one fab in one
// working set. The set powers compare (this pass) and, later, a recipe
// switcher in open/lateral/meas-hist.

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

const storageKey = (toolType: string) =>
  `skewnono:recipe-search.selection.v2.${toolType}`

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType) => {
  const entries = usePersistedState<RecipeSelectionEntry[]>(
    `recipe-search:selection:v2:${toolType}`,
    storageKey(toolType),
    { default: () => [], normalize: normalizeRecipeSelectionEntries }
  )

  const selected = computed(() => entries.value.map(entry => entry.name))
  const capabilities = computed(() => capabilitiesForRecipeSelection(entries.value))
  const has = (name: string, fabName: string) =>
    entries.value.some(entry => entry.name === name && entry.fab_name === fabName)
  const sourceOf = (name: string, fabName: string): RecipeSearchSource =>
    entries.value.find(entry => entry.name === name && entry.fab_name === fabName)?.source ?? 'redis'

  const add = (name: string, fabName: string, source: RecipeSearchSource = 'redis') => {
    entries.value = upsertRecipeSelection(entries.value, name, fabName, source)
  }

  const remove = (name: string, fabName: string) => {
    entries.value = removeRecipeSelection(entries.value, name, fabName)
  }

  const toggle = (name: string, fabName: string, source: RecipeSearchSource = 'redis') => {
    if (has(name, fabName)) remove(name, fabName)
    else add(name, fabName, source)
  }

  const clear = () => {
    entries.value = []
  }

  const promoteRedis = (rows: Array<{ recipe_name: string, fab_name: string }>) => {
    entries.value = promoteRecipeSelectionsToRedis(entries.value, rows)
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
