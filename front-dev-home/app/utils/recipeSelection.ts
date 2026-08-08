import { hasFab, normalizeFab, sameFab } from './fab.ts'
import { recipePairKey } from './recipePair.ts'

export type RecipeSearchSource = 'redis' | 'opensearch'

export interface RecipeSelectionEntry {
  name: string
  fab_name: string
  source: RecipeSearchSource
}

export interface RecipeSelectionCapabilities {
  open: boolean
  lateral: boolean
  measHist: boolean
  compare: boolean
}

const isSource = (value: unknown): value is RecipeSearchSource =>
  value === 'redis' || value === 'opensearch'

const toEntry = (value: unknown): RecipeSelectionEntry | null => {
  if (typeof value === 'string') {
    const name = value.trim()
    return name ? { name, fab_name: '', source: 'redis' } : null
  }
  if (!value || typeof value !== 'object') return null

  const candidate = value as Record<string, unknown>
  const name = typeof candidate.name === 'string' ? candidate.name.trim() : ''
  const fabName = typeof candidate.fab_name === 'string' ? candidate.fab_name.trim().toUpperCase() : ''
  return name && isSource(candidate.source)
    ? { name, fab_name: fabName, source: candidate.source }
    : null
}

export const normalizeRecipeSelectionEntries = (
  parsed: unknown
): RecipeSelectionEntry[] => {
  if (!Array.isArray(parsed)) return []
  const byKey = new Map<string, RecipeSelectionEntry>()
  for (const value of parsed) {
    const entry = toEntry(value)
    if (!entry) continue
    const key = recipePairKey(entry.fab_name, entry.name)
    const existing = byKey.get(key)
    if (!existing || entry.source === 'redis') byKey.set(key, entry)
  }
  return [...byKey.values()]
}

export const upsertRecipeSelection = (
  entries: RecipeSelectionEntry[],
  rawName: string,
  fabName: string,
  source: RecipeSearchSource
): RecipeSelectionEntry[] => {
  const name = rawName.trim()
  if (!name) return entries
  const key = recipePairKey(fabName, name)
  const index = entries.findIndex(entry => recipePairKey(entry.fab_name, entry.name) === key)
  if (index < 0) return [...entries, { name, fab_name: fabName, source }]
  if (entries[index]!.source === 'redis' || source === 'opensearch') return entries
  return entries.map((entry, at) => at === index ? { name, fab_name: fabName, source: 'redis' } : entry)
}

export const removeRecipeSelection = (
  entries: RecipeSelectionEntry[],
  name: string,
  fabName: string
): RecipeSelectionEntry[] => {
  const key = recipePairKey(fabName, name)
  return entries.filter(entry => recipePairKey(entry.fab_name, entry.name) !== key)
}

/**
 * Promote OpenSearch-sourced selections that the Redis catalog now contains.
 *
 * Matching is on the (recipe_name, fab_name) PAIR, never the bare name. A
 * recipe name is not unique across fabs — R3 and M16B share roughly a fifth of
 * their names — so a name-only lookup can adopt another fab's row and rewrite
 * the entry's own fab. Nothing errors when that happens: the compare body and
 * the `&fab_name=` owner-fab routing both follow the rewritten value, and the
 * user simply reads the wrong fab's numbers.
 *
 * An entry that carries no fab yet (`''`) is the one case a name-only lookup is
 * allowed — there is no pair to match on. Even then an ambiguous name is left
 * alone rather than guessed: unknown beats confidently wrong, and the entry
 * stays promotable on the next catalog load that resolves it.
 */
export const promoteRecipeSelectionsToRedis = (
  entries: RecipeSelectionEntry[],
  rows: Array<{ recipe_name: string, fab_name: string }>
): RecipeSelectionEntry[] => {
  // Fabs per recipe name, canonicalized — the catalog reports whatever casing
  // its source DB stores, so 'r3' and 'R3' must not read as two fabs.
  const fabsByName = new Map<string, Set<string>>()
  for (const row of rows) {
    const fab = normalizeFab(row.fab_name)
    if (!fab) continue
    const fabs = fabsByName.get(row.recipe_name)
    if (fabs) fabs.add(fab)
    else fabsByName.set(row.recipe_name, new Set([fab]))
  }

  // The fab this entry should be promoted to, or null to leave it as it is.
  const promotedFab = (entry: RecipeSelectionEntry): string | null => {
    const fabs = fabsByName.get(entry.name)
    if (!fabs) return null
    if (hasFab(entry.fab_name)) {
      // Pair-exact: the catalog must list this name under THIS entry's fab.
      const hit = [...fabs].find(fab => sameFab(fab, entry.fab_name))
      return hit ?? null
    }
    // Fab-unknown: adopt the catalog's fab only when the name names one fab.
    return fabs.size === 1 ? [...fabs][0]! : null
  }

  let changed = false
  const next = entries.map((entry) => {
    if (entry.source !== 'opensearch') return entry
    const fab = promotedFab(entry)
    if (fab === null) return entry
    changed = true
    return { ...entry, fab_name: fab, source: 'redis' as const }
  })
  return changed ? normalizeRecipeSelectionEntries(next) : entries
}

export const capabilitiesForRecipeSelection = (
  entries: RecipeSelectionEntry[]
): RecipeSelectionCapabilities => {
  if (!entries.length) {
    return { open: false, lateral: false, measHist: false, compare: false }
  }
  const redisOnly = entries.every(entry => entry.source === 'redis')
  return { open: redisOnly, lateral: true, measHist: true, compare: redisOnly }
}

export const canCompareRecipeSelection = (
  entries: RecipeSelectionEntry[]
): boolean => entries.length >= 2 && capabilitiesForRecipeSelection(entries).compare

export const recipesForCompare = (
  entries: RecipeSelectionEntry[]
): Array<{ recipe_name: string, fab_name: string }> | null =>
  canCompareRecipeSelection(entries)
    ? entries.map(entry => ({ recipe_name: entry.name, fab_name: entry.fab_name }))
    : null
