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

/** `searchText` must already be lowercased (hoisted out of the match loop). */
export const matchesRecipeQuery = (searchText: string, tokens: string[]): boolean =>
  tokens.length > 0 && tokens.every(token => searchText.includes(token))

/**
 * Distinct meas-hist full_names that satisfy the same AND-token match as the
 * catalog lookup. The meas-hist search endpoint ORs its `recipe` terms
 * server-side, so this client-side re-check restores AND semantics before the
 * UI claims "found in measurement history".
 */
export const matchingHistoryNames = (fullNames: string[], tokens: string[]): string[] => {
  const matched: string[] = []
  const seen = new Set<string>()
  for (const name of fullNames) {
    if (seen.has(name)) continue
    seen.add(name)
    if (matchesRecipeQuery(name.toLowerCase(), tokens)) matched.push(name)
  }
  return matched
}
