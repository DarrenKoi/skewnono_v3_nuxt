// Skewvoir single-MSR exact-pair relationship join.
//
// THE JOIN IS THE CRUX. Two quantities of ONE measurement are correlated only by
// pairing their values on a SHARED SITE/SEQUENCE KEY — never by array index. A
// site present in one quantity but not the other is DROPPED from the pairing and
// counted as `missing`; it is never smeared against a differently-keyed row (that
// silent index misalignment is exactly the bug this module exists to prevent).
//
// Two join shapes:
//   • CD ↔ CD   — two CD parameters of the focus MSR, paired by
//                 chip_number, then by chip_coordinate when every repeated
//                 observation has matching coordinate sets.
//   • CD ↔ FDC  — a CD parameter vs a per-sequence dynamic FDC channel of the
//                 SAME MSR, paired by sequence. This is a same-MSR + same-sequence
//                 join (flagged in the result).
//
// CRITICAL readiness: when there are ZERO pairs, or either axis is CONSTANT (zero
// variance), the answer is `평가 불가` (unavailable) — NOT a fabricated r = 0.
//
// REUSE, do not re-derive:
//   • utils/msrRows.ts — isMeasuredRow (the measured↔failure gate)
//   • utils/stats.ts   — pearson / spearman (the correlation math + null contract)
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow, type MeasuredMsrRow } from '../msrRows.ts'
import { pearson, spearman } from '../stats.ts'

export type RelationshipJoin = 'cd-cd' | 'cd-fdc'
export type RelationshipReadiness = 'ready' | 'unavailable'

/** One paired observation, keyed by its paired chip/coordinate. `chip` carries the
 * die identity so a scatter-point click can drive `setFocusedSite(chip)`. */
export interface PairedPoint {
  key: string
  chip: string
  sequence: number
  x: number
  y: number
}

export interface RelationshipResult {
  join: RelationshipJoin
  xLabel: string
  yLabel: string
  points: PairedPoint[]
  pairN: number
  // Sites present in exactly one of the two quantities — dropped from pairing.
  missingN: number
  pearson: number | null
  spearman: number | null
  readiness: RelationshipReadiness
  // Why the relationship is unavailable (null when ready). Distinguishes the two
  // honest failures — no pairs vs a constant axis — so the UI never lies with r=0.
  reason: string | null
  // Chart-meta flag.
  sameMsrSequenceJoin: boolean
}

const isConstant = (nums: number[]): boolean => {
  if (nums.length === 0) return true
  let min = nums[0]!
  let max = nums[0]!
  for (const n of nums) {
    if (n < min) min = n
    if (n > max) max = n
  }
  return min === max
}

// Resolve the honest readiness verdict + reason for a set of paired points.
// pearson/spearman already return null for n < 3 and zero-variance; readiness is
// the caller-facing verdict that turns that null into a specific, non-misleading
// reason instead of a fabricated correlation.
const assess = (points: PairedPoint[]): { readiness: RelationshipReadiness, reason: string | null } => {
  if (points.length === 0) {
    return { readiness: 'unavailable', reason: '짝지어진 관측치가 없습니다 — 평가 불가' }
  }
  if (points.length < 3) {
    return { readiness: 'unavailable', reason: `표본 부족 (n=${points.length}) — 평가 불가` }
  }
  if (isConstant(points.map(p => p.x)) || isConstant(points.map(p => p.y))) {
    return { readiness: 'unavailable', reason: '한 축의 분산이 없습니다 (상수) — 평가 불가' }
  }
  return { readiness: 'ready', reason: null }
}

const finalize = (
  join: RelationshipJoin,
  xLabel: string,
  yLabel: string,
  points: PairedPoint[],
  missingN: number
): RelationshipResult => {
  const { readiness, reason } = assess(points)
  const pairs = points.map(p => [p.x, p.y] as [number, number])
  // Only surface correlation numbers when the relationship is evaluable; a
  // constant axis or too-few pairs must read as 평가 불가, never r = 0.
  const r = readiness === 'ready' ? pearson(pairs) : null
  const rho = readiness === 'ready' ? spearman(pairs) : null
  return {
    join,
    xLabel,
    yLabel,
    points,
    pairN: points.length,
    missingN,
    pearson: r,
    spearman: rho,
    readiness,
    reason,
    // cd-fdc is BY CONSTRUCTION a same-MSR + same-sequence join, so the flag
    // is derived from the join kind — a call site cannot state it wrongly.
    sameMsrSequenceJoin: join === 'cd-fdc'
  }
}

const meanCd = (rows: MeasuredMsrRow[]): number =>
  rows.reduce((sum, row) => sum + row.cd_value, 0) / rows.length

const groupBy = (
  rows: MeasuredMsrRow[],
  keyOf: (row: MeasuredMsrRow) => string
): Map<string, MeasuredMsrRow[]> => {
  const groups = new Map<string, MeasuredMsrRow[]>()
  for (const row of rows) {
    const key = keyOf(row)
    const group = groups.get(key) ?? []
    group.push(row)
    groups.set(key, group)
  }
  return groups
}

const sameKeys = (
  left: Map<string, MeasuredMsrRow[]>,
  right: Map<string, MeasuredMsrRow[]>
): boolean =>
  left.size === right.size && [...left.keys()].every(key => right.has(key))

/**
 * Chip-based join of two CD parameters of ONE MSR. Repeated observations pair by
 * coordinate when complete matching coordinates are available; otherwise each
 * parameter is averaged into one chip-level point. Chips measured on only one
 * axis are dropped and counted as `missing`. Never pairs by array index.
 */
export const buildCdCdRelationship = (
  rows: MsrFileRow[],
  paramX: string,
  paramY: string
): RelationshipResult => {
  const measured = rows.filter(isMeasuredRow)
  const xByChip = groupBy(measured.filter(row => row.parameter === paramX), row => row.chip_number)
  const yByChip = groupBy(measured.filter(row => row.parameter === paramY), row => row.chip_number)

  const points: PairedPoint[] = []
  let missingN = 0
  for (const [chip, xRows] of xByChip) {
    const yRows = yByChip.get(chip)
    if (!yRows) {
      missingN++
      continue
    }

    if (xRows.length === 1 && yRows.length === 1) {
      points.push({
        key: chip,
        chip,
        sequence: xRows[0]!.sequence,
        x: xRows[0]!.cd_value,
        y: yRows[0]!.cd_value
      })
      continue
    }

    const coordinatesComplete = [...xRows, ...yRows]
      .every(row => row.chip_coordinate.trim().length > 0)
    const xByCoordinate = groupBy(xRows, row => row.chip_coordinate.trim())
    const yByCoordinate = groupBy(yRows, row => row.chip_coordinate.trim())

    if (coordinatesComplete && sameKeys(xByCoordinate, yByCoordinate)) {
      for (const [coordinate, coordinateXRows] of xByCoordinate) {
        const coordinateYRows = yByCoordinate.get(coordinate)!
        points.push({
          key: `${chip}#${coordinate}`,
          chip,
          sequence: Math.min(...coordinateXRows.map(row => row.sequence)),
          x: meanCd(coordinateXRows),
          y: meanCd(coordinateYRows)
        })
      }
      continue
    }

    points.push({
      key: chip,
      chip,
      sequence: Math.min(...xRows.map(row => row.sequence)),
      x: meanCd(xRows),
      y: meanCd(yRows)
    })
  }

  for (const chip of yByChip.keys()) {
    if (!xByChip.has(chip)) missingN++
  }
  points.sort((a, b) => a.sequence - b.sequence || a.key.localeCompare(b.key))

  return finalize('cd-cd', paramX, paramY, points, missingN)
}

/**
 * Exact-pair join of a CD parameter against a per-sequence dynamic FDC channel of
 * the SAME MSR, keyed by sequence (dynamic_fdc is keyed by sequence string).
 * Sequences with a measured CD but no FDC value (or vice versa) are dropped and
 * counted as `missing`. Same-MSR + same-sequence join.
 */
export const buildCdFdcRelationship = (
  rows: MsrFileRow[],
  cdParam: string,
  fdcParam: string,
  dynamicFdc: Record<string, Record<string, number>>
): RelationshipResult => {
  // Measured CD value per sequence for the chosen parameter.
  const cdBySeq = new Map<number, MeasuredMsrRow>()
  for (const r of rows) {
    if (r.parameter === cdParam && isMeasuredRow(r)) cdBySeq.set(r.sequence, r)
  }
  // Dynamic FDC value per sequence for the chosen channel.
  const fdcBySeq = new Map<number, number>()
  for (const [seqStr, channels] of Object.entries(dynamicFdc)) {
    const v = channels?.[fdcParam]
    if (v != null && Number.isFinite(v)) fdcBySeq.set(Number(seqStr), v)
  }

  const points: PairedPoint[] = []
  for (const [seq, cr] of cdBySeq) {
    const fv = fdcBySeq.get(seq)
    if (fv == null) continue
    points.push({ key: String(seq), chip: cr.chip_number, sequence: seq, x: cr.cd_value, y: fv })
  }
  points.sort((a, b) => a.sequence - b.sequence)

  let missingN = 0
  for (const seq of cdBySeq.keys()) if (!fdcBySeq.has(seq)) missingN++
  for (const seq of fdcBySeq.keys()) if (!cdBySeq.has(seq)) missingN++

  return finalize('cd-fdc', cdParam, fdcParam, points, missingN)
}
