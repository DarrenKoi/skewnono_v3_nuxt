// Narrowing a TTTM payload to the tools the user actually wants to compare.
//
// Pairwise data subsets trivially — a skew between two tools does not depend on
// who else is in the group. `consensus_deviation` does NOT: the server computed
// it against the median of the WHOLE fleet, so showing those numbers for a
// three-tool subset would answer a question the user did not ask, and a tool
// that looks off-consensus among five can be the centre of the three you kept.
//
// Re-basing is exact, and needs no extra data from the server. With
// consensus C and tool value t_i, the server ships d_i = t_i − C. For a kept
// subset S, the deviation we want is t_i − median(t_j : j ∈ S), and
//
//     d_i − median(d_j : j ∈ S) = (t_i − C) − (median(t_j : j ∈ S) − C)
//                               = t_i − median(t_j : j ∈ S)
//
// so C cancels and the raw values are never needed. The fab states its rule
// against a median, which is why this re-centres on the median rather than the
// mean.

import { median } from './stats.ts'
import { alignSkewMatrix } from './tttmGrouping.ts'
import type { SkewMatrix } from './tttmGrouping.ts'

export interface DeviationRow {
  eqp_id: string
  deviation: number
}

/**
 * Keep only `keep`'s tools, preserving the matrix's own ordering.
 *
 * Ordering by the MATRIX rather than by the argument is deliberate: a caller
 * passing ids in some other order must not be able to transpose the values
 * against their own labels. Reach for `alignSkewMatrix` — in tttmGrouping, next
 * to the fold whose invariant it satisfies — when you need the opposite:
 * several matrices forced into one shared basis. The difference is not
 * cosmetic, and it is why both exist: `align` can introduce all-null tools,
 * `subset` provably cannot.
 */
export const subsetSkewMatrix = (matrix: SkewMatrix, keep: readonly string[]): SkewMatrix => {
  const wanted = new Set(keep)
  return alignSkewMatrix(matrix, matrix.tools.filter(eqp => wanted.has(eqp)))
}

/**
 * Keep only `keep`'s tools and re-centre their deviations on the subset median.
 *
 * The full-fleet numbers are not reusable for a subset — see the header. An
 * empty selection yields an empty list rather than NaNs from an empty median.
 */
export const rebaseDeviations = (
  rows: readonly DeviationRow[],
  keep: readonly string[]
): DeviationRow[] => {
  const wanted = new Set(keep)
  const kept = rows.filter(row => wanted.has(row.eqp_id))
  if (kept.length === 0) return []

  const centre = median(kept.map(row => row.deviation))
  return kept.map(row => ({ ...row, deviation: row.deviation - centre }))
}

/**
 * The tool ids to actually render, given a stored selection.
 *
 * An empty selection means "all of them", not "none": that is what a fresh user
 * has, and it is also what makes a tool added to the fleet later show up
 * instead of being silently excluded by a selection saved before it existed.
 */
export const resolveSelection = (
  available: readonly string[],
  selected: readonly string[]
): string[] => {
  // De-duplicated because the result is used as a TOOL BASIS by
  // `alignSkewMatrix`, where a repeated id becomes a repeated row and column —
  // a matrix that reports a tool's skew against itself as if against a peer.
  // Not hypothetical: sem_list's fleet carries a handful of duplicate eqp_ids,
  // and this feature's tool list is built from the same physical fleet.
  const fleet = [...new Set(available)]
  if (selected.length === 0) return fleet
  const wanted = new Set(selected)
  const kept = fleet.filter(eqp => wanted.has(eqp))
  // Every stored id is gone (fleet replaced, or a stale fab's selection):
  // fall back to showing the fleet rather than an empty screen.
  return kept.length > 0 ? kept : fleet
}
