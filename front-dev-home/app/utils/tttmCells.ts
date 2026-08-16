// What an occupied cell looks like once its CD, its ranking index and the
// current tolerance have been resolved — and which tools that leaves out.
//
// This exists because three surfaces now argue from the same numbers: the cell
// tabs above the pairwise matrix, the 셀별 최악 장비쌍 bars beside it, and the
// 그룹에서 빠진 장비 card above both. When PairMatrix owned this privately, the
// second and third surfaces would each have had to restate `worst pair ÷ CD의
// 1%`, and a fix to one copy is a fix the other two silently miss.
//
// Pure by construction: it takes plain data, not a `SkewCondition`, so nothing
// here reaches into the API composable and every function below is testable
// without a component.

import {
  effectiveToleranceNm,
  fractionOfLimit,
  isMeasured,
  resolveNominalCd,
  worstFractionOfLimit,
  type NominalCd,
  type ToleranceIndex
} from './tttmLimits.ts'
import type { Confidence, SkewMatrix, Tier } from './tttmGrouping.ts'

/** One occupied cell, already reduced to the single matrix it reads through. */
export interface CellInput {
  cell_id: string
  beam_condition: string
  axis: string
  cd_band: string
  median_cd_nm: number | null
  tier: Tier
  confidence: Confidence
  labels: string[]
  matrix: SkewMatrix
}

/** A named pair and what it measured, in one cell. */
export interface PairReading {
  a: string
  b: string
  skewNm: number
  /** The pair as a multiple of CD's 1% — comparable across cells, unlike nm. */
  index: number
}

export interface RankedCell {
  cell: CellInput
  matrix: SkewMatrix
  cd: NominalCd
  /** Worst pair as a CD-relative index; null when nothing in the cell was measured. */
  severity: number | null
  /** The pair that severity came from, so the number on screen has names attached. */
  worstPair: PairReading | null
  /** What the current knob costs THIS cell, in its own nanometres. */
  thresholdNm: number
  /** Pairs over that threshold. The count the header chip reports. */
  failingPairs: number
}

/**
 * The worst measured pair in a cell, with both tool names.
 *
 * `maxMeasuredPair` in tttmLimits answers the same question without the names;
 * this one exists because every 3a surface quotes the pair ("BC1·Y 셀에서
 * ECDX204 와 0.240 nm"), and a number whose partner is unnamed cannot be acted
 * on. Upper triangle only — the matrix is symmetric by contract.
 */
export const worstPairOf = (matrix: SkewMatrix, cdNm: number): PairReading | null => {
  let worst: PairReading | null = null
  for (let i = 0; i < matrix.values.length; i++) {
    const cols = matrix.values[i]
    if (!cols) continue
    for (let j = i + 1; j < cols.length; j++) {
      const skew = cols[j]
      if (!isMeasured(skew)) continue
      if (worst === null || skew > worst.skewNm) {
        worst = {
          a: matrix.tools[i] ?? '',
          b: matrix.tools[j] ?? '',
          skewNm: skew,
          index: fractionOfLimit(skew, cdNm)
        }
      }
    }
  }
  return worst
}

/** Pairs whose skew exceeds this cell's own threshold. */
export const countFailingPairs = (matrix: SkewMatrix, thresholdNm: number): number => {
  let failing = 0
  for (let i = 0; i < matrix.values.length; i++) {
    const cols = matrix.values[i]
    if (!cols) continue
    for (let j = i + 1; j < cols.length; j++) {
      const skew = cols[j]
      if (isMeasured(skew) && skew > thresholdNm) failing++
    }
  }
  return failing
}

/**
 * THE ranking: cells worst-first by the CD-normalised index, never by raw nm and
 * never in payload order. A 0.13 nm pair at a 68 nm CD outranks nothing, while
 * the same 0.13 nm on the monitor wafer is most of the way to the fab's limit,
 * so sorting by nm puts them in the wrong order.
 *
 * Cells with nothing measured sort last: they carry no evidence, so they cannot
 * be "better" than a cell that does.
 *
 * The ORDER deliberately does not depend on the tolerance — only `thresholdNm`
 * and `failingPairs` do. Dragging the slider must not resort the tab strip under
 * the cursor.
 */
export const rankCells = (cells: readonly CellInput[], tolerance: ToleranceIndex): RankedCell[] =>
  cells
    .map((cell): RankedCell => {
      const cd = resolveNominalCd(cell.median_cd_nm)
      const thresholdNm = effectiveToleranceNm(tolerance, cd.nm)
      return {
        cell,
        matrix: cell.matrix,
        cd,
        severity: worstFractionOfLimit(cell.matrix.values, cd.nm),
        worstPair: worstPairOf(cell.matrix, cd.nm),
        thresholdNm,
        failingPairs: countFailingPairs(cell.matrix, thresholdNm)
      }
    })
    .sort((a, b) => (b.severity ?? -1) - (a.severity ?? -1))

/** `BC1 · Y` — the cell's identity without its CD band, for tabs and prose. */
export const cellLabel = (cell: CellInput) => `${cell.beam_condition} · ${cell.axis}`

/**
 * How far a cell's worst pair sits along a track whose tolerance mark is a third
 * of the way across, as a 0–1 fraction.
 *
 * The track spans 3× tolerance for every row, which is what lets rows at
 * different CDs be read against each other: the mark is always at the same
 * place, so a longer bar always means "further past its own limit". Normalising
 * to the largest nm instead would make a 68 nm cell's comfortable 0.062 nm look
 * like the biggest problem on the list.
 *
 * Clamped at 1 — a pair more than 3× over is off the end of the track, and the
 * caller reports the raw numbers beside the bar anyway.
 */
export const TOLERANCE_MARK = 1 / 3

export const barFraction = (skewNm: number, thresholdNm: number): number => {
  if (!(thresholdNm > 0)) return 0
  return Math.min(1, (skewNm / thresholdNm) * TOLERANCE_MARK)
}

/** A tool the primary group left out, and the pair that kept it out. */
export interface ExcludedTool {
  eqp_id: string
  /** Worst offending pair against a group MEMBER — the reason for exclusion. */
  blocker: PairReading | null
  /** The cell that pair was measured in. */
  cell: CellInput | null
  /** That cell's threshold, so the card can say what the pair exceeded. */
  thresholdNm: number
}

/**
 * Which selected tools the primary group left out, worst offender first.
 *
 * The blocking pair is searched against GROUP MEMBERS only. A tool's worst pair
 * overall may well be with another excluded tool, and quoting that would explain
 * nothing: what kept it out of the group is the closest it came to the tools
 * that are in it — reported as its own worst pair against them, since a clique
 * admits a tool only if EVERY member is inside tolerance.
 *
 * An empty `group` (no N배화 group at this tolerance) yields an empty list
 * rather than "everything is excluded": with no group to be outside of, the
 * exclusion has no meaning to report.
 */
export const excludedTools = (
  selected: readonly string[],
  group: readonly string[],
  ranked: readonly RankedCell[]
): ExcludedTool[] => {
  if (group.length === 0) return []
  const inGroup = new Set(group)

  return selected
    .filter(eqp => !inGroup.has(eqp))
    .map((eqp): ExcludedTool => {
      let blocker: PairReading | null = null
      let cell: CellInput | null = null
      let thresholdNm = 0

      for (const row of ranked) {
        const self = row.matrix.tools.indexOf(eqp)
        if (self < 0) continue
        for (let j = 0; j < row.matrix.tools.length; j++) {
          const other = row.matrix.tools[j]
          if (!other || !inGroup.has(other)) continue
          const skew = row.matrix.values[self]?.[j]
          if (!isMeasured(skew)) continue
          // Ranked by index, not nm: the pair that most exceeded ITS OWN cell's
          // allowance is the one that explains the exclusion, and two cells at
          // different CDs cannot be compared any other way.
          const index = fractionOfLimit(skew, row.cd.nm)
          if (blocker === null || index > blocker.index) {
            blocker = { a: eqp, b: other, skewNm: skew, index }
            cell = row.cell
            thresholdNm = row.thresholdNm
          }
        }
      }

      return { eqp_id: eqp, blocker, cell, thresholdNm }
    })
    .sort((a, b) => (b.blocker?.index ?? -1) - (a.blocker?.index ?? -1))
}
