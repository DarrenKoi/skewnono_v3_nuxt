// Reconciling a PERSISTED recipe pick against the recipes the fab has measured.
//
// `useTttmSettings` stores the recipe so a working setup survives a reload, and
// `normalizeScope` there checks the stored SHAPE. Nothing checked the stored
// VALUE against what the server still offers, and the two pickers resolve a
// recipe through different sources:
//
//   recipe picker  → GET /<slug>/tttm/recipes   — only what meas_hist has RUN
//   parameter list → GET /<slug>/recipe-search/parameters — needs an .idp,
//                    whose location is itself derived from a measurement
//
// So a recipeId stored while the picker still read recipe-search's catalogue
// (every recipe that EXISTS, ~50,000 per fab) names something nobody measured.
// The office answers that with a bare LookupError, which `back_dev_home` maps
// to a 502 — "No document in meas_hist_cdsem has full_name=... for fab 'R3'.
// A recipe that exists in the catalog but has never been measured has no .idp
// location to derive." Home never sees it: recipe-search's mock fabricates a
// 200 for any name it is handed.

/**
 * Whether a persisted recipe pick still stands, given the measured-recipe list.
 *
 * A predicate rather than a "return the pick that should stand" function: the
 * only two answers are the input and null, so returning a string forced the
 * caller into an identity comparison to recover the one bit it actually wanted,
 * and forced every reader to check that a THIRD value was not possible.
 *
 * @param recipeId  the persisted pick; null means 전체, which always stands.
 * @param measuredRecipeIds  every `recipe_id` the fab has measured, or **null**
 *   when the list has not answered yet — in flight, or the request failed.
 */
export const recipeStillStands = (
  recipeId: string | null,
  measuredRecipeIds: string[] | null
): boolean => {
  // 전체 is not a pick that can go stale.
  if (!recipeId) return true
  // Not an answer, so not grounds to discard the user's setup. An empty ARRAY
  // is an answer ("this fab measured nothing") and does clear the pick.
  if (measuredRecipeIds === null) return true
  // Exact match: recipe_id is the class/recipe full_name, and the bare recipe
  // half is a different identity the office refuses — see the tttm/recipes
  // commit and docs/datatables/meas_hist.txt.
  return measuredRecipeIds.includes(recipeId)
}
