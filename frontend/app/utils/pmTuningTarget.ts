// 튜닝 목표 — where the PM window should move one tool TO, per parameter.
//
// The target is the N배화 group's CENTRE OF GRAVITY: the mean position of the
// group's members in the same space the 장비 그룹 배치도 draws. Aim a tool at
// the centre and it is, by construction, no further from any member than the
// group's own spread — which is the thing a PM can actually be planned against,
// unlike a pairwise verdict that only names the one partner you are worst with.
//
// Why this is the SAME point the map's group ring is drawn around, not merely a
// similar one: `parameterPca` places tools by centring each column and
// projecting onto eigenvectors, and both steps are linear. So
//
//     mean_over_members( project(row) ) === project( mean_over_members(row) )
//
// and the centroid computed here in parameter space lands exactly on the ring's
// centre. That is asserted in the tests rather than left as a comment, because
// the whole value of this table is that it quotes a point the reader can see.
//
// Contrast `pmAdmission.ts`, which answers a different question over a
// different axis: whether every OCCUPIED CELL admits the tool. That is the
// membership verdict; this is the tuning instruction. Both are true at once and
// neither derives from the other.
//
// Pure by construction like its neighbours: plain data in, plain data out, runs
// under `node --test`, imports nothing from composables.

import { profileRows, usableColumns, type ParameterProfile } from './parameterPca.ts'
import { mean } from './stats.ts'
import { effectiveToleranceNm, fractionOfLimit, type ToleranceIndex } from './tttmLimits.ts'

/** One parameter's tuning target for the picked tool. */
export interface TuningTargetRow {
  name: string
  /** The CD this parameter's allowance is drawn against. */
  cdNm: number
  /** The picked tool's offset from the fleet median, nm. */
  currentNm: number
  /** The group's centre of gravity on this parameter, nm — the target. */
  centroidNm: number
  /** centroid − current: signed, and the instruction. + = raise, − = lower. */
  deltaNm: number
  /** What the current tolerance allows on this parameter, in its own nm. */
  toleranceNm: number
  /** |delta| as a multiple of this parameter's own action limit — the rank key. */
  index: number
  withinTolerance: boolean
}

export interface TuningTarget {
  eqp_id: string
  /** Already one of the members whose mean defines the target. */
  inGroup: boolean
  /** Group members that were placeable, and so define the centroid. */
  members: number
  /** The columns the map and this table share, in profile order. */
  parameters: string[]
  /**
   * False when the picked tool did not measure every used parameter. The map
   * cannot place it either (it is in `pca.detached`), so there is no position
   * to take a difference from and `rows` is empty.
   */
  placed: boolean
  /** Worst first, by |delta| against that parameter's own allowance. */
  rows: TuningTargetRow[]
  worst: TuningTargetRow | null
}

/**
 * The per-parameter tuning targets for one tool against the group's centroid.
 *
 * `null` when there is nothing to aim at: no usable column (no recipe picked,
 * so no parameter profile), no tool picked, or no group to have a centre. Those
 * are three different empty states and the caller words them separately — the
 * distinction it needs is carried by the inputs it already has, not by a
 * discriminated return.
 */
export const tuningTarget = (
  profile: ParameterProfile,
  selected: readonly string[],
  group: readonly string[],
  eqpId: string | null,
  tolerance: ToleranceIndex
): TuningTarget | null => {
  if (!eqpId || group.length === 0) return null

  const columns = usableColumns(profile, selected)
  if (columns.length === 0) return null
  const parameters = columns.map(c => c.name)

  // Placed under the SAME completeness rule the map uses, so the centroid is
  // the mean of the tools the map actually drew. Members the map dropped are
  // not in its ring and must not be in this mean either.
  const { placed } = profileRows(profile, columns, [...new Set([...group, eqpId])])
  const at = new Map(placed.map(p => [p.eqp_id, p.row]))

  // `.map().filter()`, never `flatMap`: a row IS an array, so flatMap would
  // splice the numbers of every member into one flat list and the "centroid"
  // would be a mean over the wrong axis.
  const memberRows = group
    .map(eqp => at.get(eqp))
    .filter((row): row is number[] => row !== undefined)
  const self = at.get(eqpId)
  const inGroup = group.includes(eqpId)

  if (memberRows.length === 0 || !self) {
    return {
      eqp_id: eqpId,
      inGroup,
      members: memberRows.length,
      parameters,
      placed: self !== undefined,
      rows: [],
      worst: null
    }
  }

  const rows = columns.map((column, j): TuningTargetRow => {
    const centroidNm = mean(memberRows.map(row => row[j]!))
    const currentNm = self[j]!
    const deltaNm = centroidNm - currentNm
    const toleranceNm = effectiveToleranceNm(tolerance, column.limitCd)
    return {
      name: column.name,
      cdNm: column.limitCd,
      currentNm,
      centroidNm,
      deltaNm,
      toleranceNm,
      index: Math.abs(fractionOfLimit(deltaNm, column.limitCd)),
      withinTolerance: Math.abs(deltaNm) <= toleranceNm
    }
  })

  // Worst first, by the CD-relative index rather than raw nm — the same
  // ranking every other TTTM surface uses, and the only one under which a
  // 68 nm feature and a 32 nm feature are comparable at all.
  rows.sort((a, b) => b.index - a.index)

  return {
    eqp_id: eqpId,
    inGroup,
    members: memberRows.length,
    parameters,
    placed: true,
    rows,
    worst: rows[0] ?? null
  }
}
