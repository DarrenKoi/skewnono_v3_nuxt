// Recent recipe-search entries. A term is only meaningful against the fab
// catalog it was typed into — the Redis list is loaded per [fab] segment, so
// replaying an R3 term while browsing M16B matches nothing and falls through
// to the OpenSearch probe. Each entry therefore carries the fabs it was
// searched in, and replaying one navigates to those fabs first.
import { canonicalFabList } from './fab.ts'

export interface RecipeRecentSearch {
  term: string
  // Canonical (uppercase, deduped) fab list. Empty = legacy v2 string entry
  // whose fab was never recorded; replay keeps whatever fab is current.
  fabs: string[]
}

export const recipeRecentSearchKey = (entry: RecipeRecentSearch): string =>
  `${entry.term.toLowerCase()}@${entry.fabs.join(',')}`

export const addRecipeRecentSearch = (
  entries: RecipeRecentSearch[],
  entry: RecipeRecentSearch,
  maxEntries: number
): RecipeRecentSearch[] => {
  const key = recipeRecentSearchKey(entry)
  return [entry, ...entries.filter(existing => recipeRecentSearchKey(existing) !== key)]
    .slice(0, maxEntries)
}

// Storage normalizer. Accepts the v2 shape (bare strings) so an upgrade does
// not erase the user's list; those entries simply have no fab to switch to.
export const normalizeRecipeRecentSearches = (parsed: unknown): RecipeRecentSearch[] => {
  if (!Array.isArray(parsed)) return []
  const out: RecipeRecentSearch[] = []
  for (const raw of parsed) {
    if (typeof raw === 'string') {
      if (raw.trim()) out.push({ term: raw, fabs: [] })
      continue
    }
    if (typeof raw !== 'object' || raw === null) continue
    const item = raw as Record<string, unknown>
    if (typeof item.term !== 'string' || !item.term.trim()) continue
    const fabs = Array.isArray(item.fabs) ? canonicalFabList(item.fabs.filter(f => typeof f === 'string')) : []
    out.push({ term: item.term, fabs })
  }
  return out
}
