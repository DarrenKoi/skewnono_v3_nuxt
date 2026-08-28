// Reconciling a PERSISTED scope pick against what the server still offers.
//
// `useTttmSettings` stores the recipe and parameter so a working setup survives
// a reload, and `normalizeScope` there checks the stored SHAPE. Nothing checked
// the stored VALUE against what the server still offers, and both picks can go
// stale on their own:
//
//   recipe     → GET /<slug>/tttm/recipes — only what meas_hist has RUN. A
//                recipeId stored while the picker still read recipe-search's
//                catalogue (every recipe that EXISTS, ~50,000 per fab) names
//                something nobody measured. The office answers that with a bare
//                LookupError, which `back_dev_home` maps to a 502 — "No document
//                in meas_hist_cdsem has full_name=... for fab 'R3'." Home never
//                sees it: recipe-search's mock fabricates a 200 for any name.
//   parameter  → `parameters` on the check payload itself — the names measured
//                under the picked recipe, read off the same rows the skew is.
//                A recipe survives an .idp revision that renames or drops one of
//                its features, and the stored parameter then names nothing; the
//                office filters its rows to that name, finds none, and answers
//                an empty grid that blames the recipe.

/**
 * Whether a persisted pick still stands, given the list the server now offers.
 *
 * One law for both halves of the scope. A predicate rather than a "return the
 * pick that should stand" function: the only two answers are the input and
 * null, so returning a string forced the caller into an identity comparison to
 * recover the one bit it actually wanted, and forced every reader to check
 * that a THIRD value was not possible.
 *
 * @param pick  the persisted pick; null means 전체, which always stands.
 * @param offered  everything the server offers, or **null** when the list has
 *   not answered yet — in flight, failed, or answering a different question.
 */
export const pickStillStands = (
  pick: string | null,
  offered: string[] | null
): boolean => {
  // 전체 is not a pick that can go stale.
  if (!pick) return true
  // Not an answer, so not grounds to discard the user's setup. An empty ARRAY
  // is an answer ("nothing offered") and does clear the pick.
  if (offered === null) return true
  // Exact match. For the recipe: recipe_id is the class/recipe full_name, and
  // the bare recipe half is a different identity the office refuses — see the
  // tttm/recipes commit and docs/datatables/hitachi/meas_hist.txt.
  return offered.includes(pick)
}

/**
 * The parameter picks that still stand — `pickStillStands` over a list.
 *
 * Several parameters can be picked, and each goes stale on its own; the ones
 * the server no longer offers are dropped and the rest kept in order. Returns
 * the SAME array when nothing changed, so a caller can watch for identity and
 * not rewrite the store on every payload.
 */
export const standingPicks = (
  picks: readonly string[],
  offered: string[] | null
): readonly string[] => {
  if (offered === null) return picks
  const kept = picks.filter(pick => offered.includes(pick))
  return kept.length === picks.length ? picks : kept
}

/** The slice of the check payload the parameter reconciliation reads. */
export interface ParameterAnswer {
  available: boolean
  recipe_id: string | null
  parameters: string[]
}

/**
 * The parameter list the picked recipe's payload offers — or null when the
 * payload on hand is not an answer to that question.
 *
 * Three ways it is not: no payload yet; a payload still describing the recipe
 * the user just LEFT (useAsyncData keeps the old data while the next request is
 * in flight, so the list on screen can belong to a recipe nobody is looking
 * at); and an unavailable payload, whose `parameters: []` is the contract's
 * "nothing to compare" rather than "this recipe has no features" — reading it
 * as an answer would erase a working pick on a window with no runs.
 */
export const offeredParameters = (
  payload: ParameterAnswer | null | undefined,
  recipeId: string | null
): string[] | null => {
  if (!recipeId || !payload || !payload.available) return null
  if (payload.recipe_id !== recipeId) return null
  return payload.parameters
}

/**
 * Why the 분석 조건 controls are inert, or null when they are live.
 *
 * `no-recipe`: the first step is not taken. `loading`: there is no answer for
 * this recipe yet and the request is in flight — the only state that is inert
 * for a moment rather than for a reason. `no-data`: there is no answer and
 * nothing in flight — the recipe's answer was unavailable, or the request
 * failed — so there is no row set to list features from and no parameter or
 * tolerance can turn it into a comparison; the results area below says which.
 *
 * Decided from `offered` (already reconciled against the picked recipe by
 * `offeredParameters`) rather than from the payload directly: useAsyncData
 * keeps the previous recipe's payload on screen while the next request runs,
 * and reading its `available` here would report the OLD recipe's verdict as
 * the new one's. An answer for this recipe keeps the controls live even while
 * a refetch (the parameter filter) is in flight.
 */
export type AnalysisLock = 'no-recipe' | 'no-request' | 'no-data' | 'loading' | null

/**
 * @param requested  whether the payload on hand was asked for THIS scope. The
 *   on-demand page (TTTM since 2026-08-28) passes `!stale`; a page that still
 *   auto-fetches passes nothing. Without it a scope nobody has requested yet
 *   would read as `no-data` — "the server found nothing" — when the truth is
 *   that the server was never asked, and the caption sends the reader to the
 *   wrong remedy.
 */
export const analysisLock = (
  recipeId: string | null,
  pending: boolean,
  offered: string[] | null,
  requested = true
): AnalysisLock => {
  if (!recipeId) return 'no-recipe'
  if (offered !== null) return null
  if (pending) return 'loading'
  return requested ? 'no-data' : 'no-request'
}
