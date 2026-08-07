/**
 * A recipe's identity anywhere multi-fab code needs a string key — Map/Set
 * keys, `v-for` keys, fetch/detail cache keys, dedupe sets. Backend
 * `recipe_id` equals `recipe_name` and is NOT scoped by fab: the same name
 * can legitimately exist once per fab, so keying on the bare name silently
 * merges two different recipes.
 *
 * One exported function so the convention cannot fork again (it had forked
 * into `${fab}|${name}` and `${fab}:${id}` before this file existed). `|` is
 * safe as the separator: fab names are short uppercase codes (R3, M16B) and
 * recipe names are `_`-delimited tool identifiers — neither contains `|`.
 * Callers that JOIN several pair keys into one string must use a different
 * character (`,` by convention), never `|` again.
 */
export const recipePairKey = (fabName: string, recipeName: string): string =>
  `${fabName}|${recipeName}`

/**
 * A SET of recipes as one cache-key string: sorted pair keys joined by `,`
 * (the sanctioned joiner — see above). Sorted so the same selection maps to
 * the same key regardless of pick order.
 */
export const recipePairSetKey = (
  refs: Array<{ fab_name: string, recipe_name: string }>
): string =>
  refs.map(r => recipePairKey(r.fab_name, r.recipe_name)).sort().join(',')
