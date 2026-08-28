// Pure logic for the pm-planning page: what it would take for one tool — the one
// in (or fresh out of) its PM window — to be ADMITTED into the current N배화
// group.
//
// PM is the rare hardware-tuning window, so the question this module answers
// is prospective: "tune which cells, by how much, and the group grows from N
// to N+1". The grouping itself is tttmGrouping's business (maximal cliques);
// this module only restates the clique's admission rule for a single
// candidate: a measured, in-tolerance pair with EVERY member, in EVERY
// occupied cell.
//
// Pure by construction, like tttmCells: takes plain data, runs under
// `node --test`, imports nothing from composables.

import { fractionOfLimit, isMeasured } from './tttmLimits.ts'
import type { CellInput, PairReading, RankedCell } from './tttmCells.ts'

/** One cell's admission verdict for the candidate tool. */
export interface CellAdmission {
  cell: CellInput
  /** The cell's own nm allowance at the current tolerance. */
  thresholdNm: number
  /** Worst measured pair against a group MEMBER — the pair to tune on. */
  worst: PairReading | null
  /** Member pairs over the threshold in this cell. */
  failingPairs: number
  /** Members with no measured pair here — unmeasured also blocks admission. */
  unmeasured: string[]
  /** nm the worst member pair must come down for this cell to pass. 0 = passes. */
  requiredNm: number
  admitted: boolean
}

export interface AdmissionReport {
  eqp_id: string
  /** Already a member — nothing to tune, N is already counted. */
  inGroup: boolean
  /** Every occupied cell admits the tool (vacuously true for a member). */
  admitted: boolean
  /**
   * Cells still blocking admission (0 for a member). The report carries its
   * own headline number rather than leaving each caller to recompute
   * `filter(!admitted).length` — two independent copies is how they start
   * disagreeing.
   *
   * Only PmPlanningView's summary bar renders "미충족 셀 N개" since 2026-08-28;
   * the 튜닝 목표 card, which used to render the second copy, now states a
   * distance to the group centroid instead and no longer reads this report.
   * The field stays the single source anyway: one renderer today is not a
   * reason to hand the next one a recomputation.
   */
  blockedCells: number
  /** Non-member only: per-cell tuning targets, worst first. */
  cells: CellAdmission[]
}

/**
 * Which tool the page opens on.
 *
 * The story of the page is "the tool fresh out of its PM window is the one
 * being tuned", so the most recent `post_pm_at` wins (ISO strings compare
 * lexicographically). With no PM date anywhere, the first `fallback` entry —
 * the caller passes its worst-excluded tool, the next best story — then the
 * roster's first tool, then null for an empty fab.
 */
export const pickDefaultTool = (
  tools: readonly { eqp_id: string, post_pm_at: string | null }[],
  fallback: readonly string[]
): string | null => {
  let latest: { eqp_id: string, post_pm_at: string } | null = null
  for (const tool of tools) {
    if (tool.post_pm_at === null) continue
    if (
      latest === null
      || tool.post_pm_at > latest.post_pm_at
      // Deterministic tie-break, so two tools sharing a PM date cannot swap
      // the default between visits.
      || (tool.post_pm_at === latest.post_pm_at && tool.eqp_id < latest.eqp_id)
    ) {
      latest = { eqp_id: tool.eqp_id, post_pm_at: tool.post_pm_at }
    }
  }
  return latest?.eqp_id ?? fallback[0] ?? tools[0]?.eqp_id ?? null
}

/**
 * The admission report for one candidate against the current primary group.
 *
 * `null` when there is no group: with nothing to be admitted INTO, a report
 * would have no meaning (same stance as tttmCells' `excludedTools`).
 */
export const admissionReport = (
  eqpId: string,
  group: readonly string[],
  ranked: readonly RankedCell[]
): AdmissionReport | null => {
  if (group.length === 0) return null

  if (group.includes(eqpId)) {
    return {
      eqp_id: eqpId,
      inGroup: true,
      admitted: true,
      blockedCells: 0,
      cells: []
    }
  }

  const members = group.filter(member => member !== eqpId)
  const cells = ranked.map((row): CellAdmission => {
    // Index map per cell, same shape as tttmGrouping's alignSkewMatrix — not
    // for speed at this fleet size, but so the three modules that walk a
    // matrix by tool name all do it the same way.
    const at = new Map(row.matrix.tools.map((eqp, index) => [eqp, index]))
    const self = at.get(eqpId) ?? -1
    let worst: PairReading | null = null
    let failingPairs = 0
    const unmeasured: string[] = []

    for (const member of members) {
      const other = at.get(member) ?? -1
      const skew = self < 0 ? null : row.matrix.values[self]?.[other]
      if (other < 0 || !isMeasured(skew)) {
        unmeasured.push(member)
        continue
      }
      if (skew > row.thresholdNm) failingPairs++
      // Worst by nm is worst by index here — one CD divides every pair in a
      // cell — and the index rides along so cells stay comparable to each other.
      if (worst === null || skew > worst.skewNm) {
        worst = { a: eqpId, b: member, skewNm: skew, index: fractionOfLimit(skew, row.cd.nm) }
      }
    }

    const requiredNm = worst === null ? 0 : Math.max(0, worst.skewNm - row.thresholdNm)
    return {
      cell: row.cell,
      thresholdNm: row.thresholdNm,
      worst,
      failingPairs,
      unmeasured,
      requiredNm,
      admitted: failingPairs === 0 && unmeasured.length === 0
    }
  })

  return {
    eqp_id: eqpId,
    inGroup: false,
    admitted: cells.length > 0 && cells.every(row => row.admitted),
    blockedCells: cells.filter(row => !row.admitted).length,
    // Worst first, by how far past its own cell's allowance the blocking pair
    // sits — the same CD-relative ranking every tttm surface uses. Cells with
    // nothing measured sort last: no evidence cannot outrank evidence.
    cells: cells.sort((a, b) => (b.worst?.index ?? -1) - (a.worst?.index ?? -1))
  }
}
