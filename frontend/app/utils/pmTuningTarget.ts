// 튜닝 목표 — where the PM window should move one tool TO, per parameter.
//
// The target is a REFERENCE CENTRE the picked tool is not part of, per
// parameter, in the same nm the 장비 그룹 배치도 places tools by:
//
//   - with an N배화 group: the MEAN of the OTHER members on that parameter.
//     Leave-one-out, because "move to the group" is a question about the other
//     tools' positions; an inclusive mean drags the target toward the tool being
//     tuned and understates its delta by (n-1)/n. Reaching the LOO target makes
//     the inclusive mean land on the same point, so the map's green cross (the
//     inclusive centroid, see FleetMap.groupCentroid) and this table agree
//     after the move, not before — the card labels the target so a reader
//     does not expect the two to coincide.
//   - with NO group at the current tolerance: the per-parameter MEDIAN of the
//     other compared tools. Median rather than mean because the tool being
//     tuned is often the outlier, and the fleet's mean would lean toward it.
//     The card says this is not an N배화 centre. Zero is NOT used: the profile
//     is an offset from the WHOLE fleet's median, not from the compared subset.
//
// Missing values are handled per COLUMN: a reference tool that did not measure
// parameter j drops out of j's centre only, and a picked tool that did not
// measure j gets no row for j (listed in `unmeasured`). The map keeps its
// whole-row completeness rule — a point needs every coordinate — but a table
// of independent per-parameter instructions does not, and gating the whole
// card on one hole is what left it blank.
//
// The tolerance never decides WHETHER a number is shown. It sets the group
// (upstream) and colours the verdict per row; that is all.
//
// Contrast `pmAdmission.ts`, which answers a different question over a
// different axis: whether every OCCUPIED CELL admits the tool. That is the
// membership verdict; this is the tuning instruction.
//
// Pure by construction like its neighbours: plain data in, plain data out, runs
// under `node --test`, imports nothing from composables.

import { usableColumns, type ParameterProfile } from './parameterPca.ts'
import { mean, median } from './stats.ts'
import { effectiveToleranceNm, fractionOfLimit, isMeasured, type ToleranceIndex } from './tttmLimits.ts'

/** One parameter's tuning target for the picked tool. */
export interface TuningTargetRow {
  name: string
  /** The CD this parameter's allowance is drawn against. */
  cdNm: number
  /** The picked tool's offset from the fleet median, nm. */
  currentNm: number
  /** The reference centre on this parameter, nm — the target. */
  centroidNm: number
  /** Reference tools that measured this parameter (never the picked tool). */
  refs: number
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
  /** 'group': LOO mean of the N배화 group. 'basis': median of the other compared tools. */
  source: 'group' | 'basis'
  /** Already one of the group's members (always false for 'basis'). */
  inGroup: boolean
  /** The columns the map and this table share, in profile order. */
  parameters: string[]
  /** Used columns with no row: the picked tool, or every reference, did not measure them. */
  unmeasured: string[]
  /** Worst first, by |delta| against that parameter's own allowance. */
  rows: TuningTargetRow[]
  worst: TuningTargetRow | null
}

/**
 * The per-parameter tuning targets for one tool.
 *
 * `null` only when there is nothing to compute over: no tool picked, or no
 * usable column (no recipe, so no profile). A group is NOT required — `basis`
 * (the compared tools) stands in, and `source` says which one answered.
 */
export const tuningTarget = (
  profile: ParameterProfile,
  selected: readonly string[],
  group: readonly string[],
  basis: readonly string[],
  eqpId: string | null,
  tolerance: ToleranceIndex
): TuningTarget | null => {
  if (!eqpId) return null

  const columns = usableColumns(profile, selected)
  if (columns.length === 0) return null
  const parameters = columns.map(c => c.name)

  const source = group.length > 0 ? 'group' : 'basis'
  const inGroup = group.includes(eqpId)
  const refTools = (source === 'group' ? group : basis).filter(eqp => eqp !== eqpId)
  const centre = source === 'group' ? mean : median

  const rowOf = new Map(profile.tools.map((eqp, i) => [eqp, i]))
  const valueOf = (eqp: string, index: number): number | null => {
    const r = rowOf.get(eqp)
    const v = r === undefined ? undefined : profile.values[r]?.[index]
    return isMeasured(v) ? v : null
  }

  const rows: TuningTargetRow[] = []
  const unmeasured: string[] = []
  for (const column of columns) {
    const currentNm = valueOf(eqpId, column.index)
    const refValues = refTools
      .map(eqp => valueOf(eqp, column.index))
      .filter((v): v is number => v !== null)
    // No current value, or no reference on this parameter: nothing to aim
    // from or at, and a NaN row would render as "NaN nm". Named rather than
    // dropped, so the reader knows the parameter was asked for.
    if (currentNm === null || refValues.length === 0) {
      unmeasured.push(column.name)
      continue
    }
    const centroidNm = centre(refValues)
    const deltaNm = centroidNm - currentNm
    const toleranceNm = effectiveToleranceNm(tolerance, column.limitCd)
    rows.push({
      name: column.name,
      cdNm: column.limitCd,
      currentNm,
      centroidNm,
      refs: refValues.length,
      deltaNm,
      toleranceNm,
      index: Math.abs(fractionOfLimit(deltaNm, column.limitCd)),
      withinTolerance: Math.abs(deltaNm) <= toleranceNm
    })
  }

  // Worst first, by the CD-relative index rather than raw nm — the same
  // ranking every other TTTM surface uses, and the only one under which a
  // 68 nm feature and a 32 nm feature are comparable at all.
  rows.sort((a, b) => b.index - a.index)

  return {
    eqp_id: eqpId,
    source,
    inGroup,
    parameters,
    unmeasured,
    rows,
    worst: rows[0] ?? null
  }
}
