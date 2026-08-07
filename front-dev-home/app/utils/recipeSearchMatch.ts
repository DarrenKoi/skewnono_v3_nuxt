import type { RecipeSearchSource } from '~/utils/recipeSelection'
import { recipePairKey } from './recipePair.ts'

/**
 * Recipe-name search matching.
 *
 * Recipe names are `_`-delimited (the segments carry meaning — e.g. the
 * manufacturing tech code), so a raw `includes()` on the whole query fails
 * the moment the user types across segment boundaries or in a different
 * segment order. Instead the query is tokenized on whitespace AND
 * underscores, and a name matches when EVERY token appears somewhere in it
 * (AND composition, case-insensitive). This is a strict relaxation of the
 * old contiguous-substring behavior: any name containing `"cd_bias"`
 * contains both `"cd"` and `"bias"`, so no previously-matching query loses
 * results.
 */

export const tokenizeRecipeQuery = (query: string): string[] =>
  query.trim().toLowerCase().split(/[\s_]+/).filter(Boolean)

export const isRecipeQueryEligible = (query: string): boolean =>
  tokenizeRecipeQuery(query).reduce((count, token) => count + token.length, 0) >= 3

/** `searchText` must already be lowercased (hoisted out of the match loop). */
export const matchesRecipeQuery = (searchText: string, tokens: string[]): boolean =>
  tokens.length > 0 && tokens.every(token => searchText.includes(token))

/**
 * Filter and rank recipe identifiers in one stable linear pass:
 * exact → prefix → substring → unordered token-only.
 * Candidate searchText values must already be trimmed and lowercased so a
 * catalog can cache normalization independently of query changes.
 */
export const rankRecipeMatches = <T>(
  candidates: Array<{ value: T, searchText: string }>,
  query: string
): T[] => {
  const normalizedQuery = query.trim().toLowerCase()
  const tokens = tokenizeRecipeQuery(query)
  const buckets: T[][] = [[], [], [], []]

  for (const candidate of candidates) {
    const searchText = candidate.searchText
    if (!matchesRecipeQuery(searchText, tokens)) continue

    const rank = searchText === normalizedQuery
      ? 0
      : searchText.startsWith(normalizedQuery)
        ? 1
        : searchText.includes(normalizedQuery)
          ? 2
          : 3
    buckets[rank]!.push(candidate.value)
  }

  return buckets.flat()
}

/** One snapshot entry: a distinct meas-hist full_name and the fab it was
 * measured in. `fab_name` is `''` when the owner is unknown — a legacy
 * names-only backend, or office documents with no fab field. */
export interface RecipeNamePair {
  recipe_name: string
  fab_name: string
}

const dedupePairs = (pairs: RecipeNamePair[]): RecipeNamePair[] => {
  const seen = new Set<string>()
  const out: RecipeNamePair[] = []
  for (const pair of pairs) {
    const key = recipePairKey(pair.fab_name, pair.recipe_name)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(pair)
  }
  return out
}

/**
 * Distinct meas-hist (full_name, fab) pairs that satisfy the same AND-token
 * match as the catalog lookup. The meas-hist search endpoint ORs its
 * `recipe` terms server-side, so this client-side re-check restores AND
 * semantics before the UI claims "found in measurement history".
 */
export const matchingHistoryPairs = (
  pairs: RecipeNamePair[],
  tokens: string[]
): RecipeNamePair[] =>
  dedupePairs(pairs).filter(pair => matchesRecipeQuery(pair.recipe_name.toLowerCase(), tokens))

/** A raw `recipe_names` entry as a pair — `{full_name, fab_name}` objects
 * from the current backend, bare name strings from a stale office adapter
 * (fab unknown). Anything else is invalid and poisons the snapshot. */
const toSnapshotPair = (value: unknown): RecipeNamePair | null => {
  if (typeof value === 'string') {
    const name = value.trim()
    return name ? { recipe_name: name, fab_name: '' } : null
  }
  if (!value || typeof value !== 'object') return null
  const candidate = value as Record<string, unknown>
  if (typeof candidate.full_name !== 'string' || !candidate.full_name.trim()) return null
  if (typeof candidate.fab_name !== 'string') return null
  return {
    recipe_name: candidate.full_name.trim(),
    fab_name: candidate.fab_name.trim().toUpperCase()
  }
}

export const normalizeRecipeNameSnapshot = (input: {
  recipe_names?: unknown
  recipe_names_complete?: unknown
  rows: Array<{ full_name?: unknown, fab_name?: unknown }>
}): { pairs: RecipeNamePair[], complete: boolean } => {
  const rowPairs = dedupePairs(input.rows.flatMap((row) => {
    if (typeof row.full_name !== 'string' || !row.full_name.trim()) return []
    const fab = typeof row.fab_name === 'string' ? row.fab_name.trim().toUpperCase() : ''
    return [{ recipe_name: row.full_name.trim(), fab_name: fab }]
  }))

  if (!Array.isArray(input.recipe_names)) {
    return {
      pairs: rowPairs,
      complete: false
    }
  }

  const pairs = input.recipe_names
    .map(toSnapshotPair)
    .filter((pair): pair is RecipeNamePair => pair !== null)
  if (pairs.length !== input.recipe_names.length) {
    return {
      pairs: dedupePairs([...pairs, ...rowPairs]),
      complete: false
    }
  }

  return {
    pairs: dedupePairs(pairs),
    complete: input.recipe_names_complete === true
  }
}

export interface RecipeSearchResult {
  recipe_name: string
  fab_name: string
  source: RecipeSearchSource
}

export const toRecipeSearchResults = (
  rows: Array<{ recipe_name: string, fab_name: string }>,
  source: RecipeSearchSource
): RecipeSearchResult[] => {
  const seen = new Set<string>()
  const results: RecipeSearchResult[] = []
  for (const row of rows) {
    const recipeName = row.recipe_name.trim()
    if (!recipeName) continue
    const fabName = (row.fab_name ?? '').trim().toUpperCase()
    const key = recipePairKey(fabName, recipeName)
    if (seen.has(key)) continue
    seen.add(key)
    results.push({ recipe_name: recipeName, fab_name: fabName, source })
  }
  return results
}

export const shouldProbeRecipeFallback = (input: {
  canSearch: boolean
  catalogPending: boolean
  redisMatchCount: number
}): boolean =>
  input.canSearch && !input.catalogPending && input.redisMatchCount === 0

export const activeRecipeResults = (
  redisResults: RecipeSearchResult[],
  fallbackResults: RecipeSearchResult[]
): RecipeSearchResult[] => {
  return redisResults.length ? redisResults : fallbackResults
}

export type RecipeSearchViewState
  = | 'idle'
    | 'catalog-loading'
    | 'fallback-loading'
    | 'results'
    | 'empty'
    | 'fallback-incomplete'
    | 'fallback-error'
    | 'sources-error'

export const resolveRecipeSearchViewState = (input: {
  canSearch: boolean
  catalogPending: boolean
  catalogFailed: boolean
  resultCount: number
  fallbackPending: boolean
  fallbackSettled: boolean
  fallbackFailed: boolean
  fallbackTruncated: boolean
}): RecipeSearchViewState => {
  if (!input.canSearch) return 'idle'
  if (input.resultCount > 0) return 'results'
  if (input.catalogPending) return 'catalog-loading'
  if (input.fallbackPending || !input.fallbackSettled) return 'fallback-loading'
  if (input.fallbackFailed) {
    return input.catalogFailed ? 'sources-error' : 'fallback-error'
  }
  if (input.fallbackTruncated) return 'fallback-incomplete'
  return 'empty'
}
