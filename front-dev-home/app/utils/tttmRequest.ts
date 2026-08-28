// The on-demand skew request: what the TTTM page sends, and whether the
// payload on hand still answers the scope on screen.
//
// Since 2026-08-28 the check is NOT re-fetched on every scope change. At the
// office one answer costs hundreds of MinIO GETs, one per run per tool, and the
// old auto-fetch paid that on page load (for a fleet-wide answer nobody had
// asked for yet) and again on every dropdown click. Now the user states the
// scope — recipe, tools, window — and asks once; the server narrows the fleet
// to the requested `eqp_id`s before it gathers a single run.
//
// That leaves a payload that can lag the scope, and the page has to SAY so
// rather than quietly render an old answer under new labels. `checkIsStale` is
// that one comparison, read from what the payload itself echoes (recipe,
// parameters, window, the narrowed roster) so no extra "last requested"
// state has to be kept in step with it.

import type { ToolRef } from '~/composables/useTttmApi'

/** The slice of the check payload the staleness law reads. */
export interface CheckEcho {
  recipe_id: string | null
  selected_parameters: string[]
  window_weeks: number
  tools: { eqp_id: string }[]
}

export interface RequestScope {
  recipeId: string | null
  parameters: readonly string[]
  windowWeeks: number
  /** The tools the request would name — the picker's resolved selection. */
  tools: readonly string[]
}

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && new Set(a).size === new Set([...a, ...b]).size

/**
 * Whether the scope on screen differs from the one the payload answers —
 * including "there is no payload", which is stale in the sense that matters:
 * the results area has nothing honest to draw.
 *
 * Set comparisons, not positional: the picker orders ids by fleet and the
 * server echoes them in roster order, and the two must not read as a change.
 */
export const checkIsStale = (
  payload: CheckEcho | null | undefined,
  scope: RequestScope
): boolean => {
  if (!payload) return true
  if (payload.recipe_id !== scope.recipeId) return true
  if (payload.window_weeks !== scope.windowWeeks) return true
  if (!sameSet(payload.selected_parameters, scope.parameters)) return true
  return !sameSet(payload.tools.map(t => t.eqp_id), scope.tools)
}

/**
 * The fab's roster for the picker, from sem-list rows already filtered to the
 * (tool type, fab) — the client-side statement of back_dev_home's
 * sem_list/roster.py law: dedupe by eqp_id, sort by eqp_id.
 *
 * Read from sem-list rather than from the check payload because the payload
 * is what the picker now REQUESTS; a roster that only arrived with the answer
 * would leave nothing to pick from before the first request. sem-list is one
 * cached fetch shared by the whole app.
 */
export const rosterFromSemList = (
  rows: readonly { eqp_id: string, eqp_model_cd: string }[]
): ToolRef[] => {
  const byId = new Map<string, ToolRef>()
  for (const row of rows) {
    if (byId.has(row.eqp_id)) continue
    byId.set(row.eqp_id, { eqp_id: row.eqp_id, label: row.eqp_id, eqp_model_cd: row.eqp_model_cd })
  }
  return [...byId.values()].sort((a, b) => a.eqp_id.localeCompare(b.eqp_id))
}
