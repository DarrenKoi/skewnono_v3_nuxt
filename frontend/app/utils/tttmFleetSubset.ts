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
 * Picking is opt-in (2026-09-11): a fresh user starts with NOTHING selected
 * and adds tools, because choosing a few from a fab's ~18 is easier than
 * clearing the rest. There is no "all" value any more — 전체 선택 writes the
 * ids — so an empty or wholly stale selection resolves to none, and the views
 * answer it with "2대 이상이어야 합니다" rather than a comparison.
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
  const wanted = new Set(selected)
  return [...new Set(available)].filter(eqp => wanted.has(eqp))
}

/** Each tool's median daily residual over the payload's collection window.
 * Missing/non-finite readings stay absent; callers rebase on their own basis.
 */
export const windowResiduals = (
  trend: readonly { eqp_id: string, skew: number }[]
): DeviationRow[] => {
  const byTool = new Map<string, number[]>()
  for (const point of trend) {
    if (!Number.isFinite(point.skew)) continue
    const values = byTool.get(point.eqp_id) ?? []
    values.push(point.skew)
    byTool.set(point.eqp_id, values)
  }
  return [...byTool].map(([eqp_id, values]) => ({ eqp_id, deviation: median(values) }))
}
