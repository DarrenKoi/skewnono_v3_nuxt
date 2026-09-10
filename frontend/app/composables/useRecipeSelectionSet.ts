// Per-toolType persistent recipe working set, persisted via usePersistedState
// so the set survives full reloads. Selection identity is the (name, fab)
// pair — the same recipe name can be selected from more than one fab in one
// working set. The set powers compare (this pass) and, later, a recipe
// switcher in open/lateral/meas-hist.

import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { hasFab, normalizeFab, sameFab } from '~/utils/fab'
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

  // Pair equality, with the casing rule utils/fab.ts mandates: a stored fab and
  // a backend-supplied one can differ in case and still be the same fab, and a
  // raw `===` would then report "not selected" for a row that is. `sameFab`
  // alone is not enough here — it answers false for a blank fab, but a blank IS
  // the identity of a legacy migrated entry, so blank-to-blank must still match
  // or `toggle` would neither find nor be able to re-add such an entry.
  const isPair = (entry: RecipeSelectionEntry, name: string, fabName: string) =>
    entry.name === name
    && (hasFab(fabName) || hasFab(entry.fab_name)
      ? sameFab(entry.fab_name, fabName)
      : true)

  const has = (name: string, fabName: string) =>
    entries.value.some(entry => isPair(entry, name, fabName))
  const sourceOf = (name: string, fabName: string): RecipeSearchSource =>
    entries.value.find(entry => isPair(entry, name, fabName))?.source ?? 'redis'

  // upsert/remove key on the raw fab string (recipePairKey is a concat), so the
  // fab is canonicalized here — at the composable's boundary — or a lowercase
  // caller would add a second entry beside the one `has` just matched.
  const add = (name: string, fabName: string, source: RecipeSearchSource = 'redis') => {
    entries.value = upsertRecipeSelection(entries.value, name, normalizeFab(fabName), source)
  }

  const remove = (name: string, fabName: string) => {
    entries.value = removeRecipeSelection(entries.value, name, normalizeFab(fabName))
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
