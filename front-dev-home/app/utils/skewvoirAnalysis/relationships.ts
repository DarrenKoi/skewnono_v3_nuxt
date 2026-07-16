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
//                 PhysicalSiteKey-minus-parameter (chip_number + sequence).
//   • CD ↔ FDC  — a CD parameter vs a per-sequence dynamic FDC channel of the
//                 SAME MSR, paired by sequence. This is a same-MSR + same-sequence
//                 join (flagged in the result), and on the Phase-1 home mock CD and
//                 dynamic FDC are coupled through a shared `health` scalar, so the
//                 result is flagged `demoCoupled` — the correlation is NOT method-
//                 validated evidence.
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

/** One paired observation, keyed by the shared site/sequence. `chip` carries the
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
  // Chart-meta flags.
  sameMsrSequenceJoin: boolean
  demoCoupled: boolean
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
  missingN: number,
  meta: { sameMsrSequenceJoin: boolean, demoCoupled: boolean }
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
    sameMsrSequenceJoin: meta.sameMsrSequenceJoin,
    demoCoupled: meta.demoCoupled
  }
}

// The PhysicalSiteKey minus the parameter: a physical site within one MSR is a
// (chip_number, sequence) pair. Two different CD parameters measured at the same
// physical site share this key.
const siteKey = (row: MsrFileRow): string => `${row.chip_number}#${row.sequence}`

/**
 * Exact-pair join of two CD parameters of ONE MSR, keyed by (chip + sequence).
 * Sites measured for only one of the two parameters are dropped and counted as
 * `missing`. Never pairs by array index.
 */
export const buildCdCdRelationship = (
  rows: MsrFileRow[],
  paramX: string,
  paramY: string
): RelationshipResult => {
  const xByKey = new Map<string, MeasuredMsrRow>()
  const yByKey = new Map<string, MeasuredMsrRow>()
  for (const r of rows) {
    if (!isMeasuredRow(r)) continue
    if (r.parameter === paramX) xByKey.set(siteKey(r), r)
    if (r.parameter === paramY) yByKey.set(siteKey(r), r)
  }

  const points: PairedPoint[] = []
  for (const [key, xr] of xByKey) {
    const yr = yByKey.get(key)
    if (!yr) continue
    points.push({ key, chip: xr.chip_number, sequence: xr.sequence, x: xr.cd_value, y: yr.cd_value })
  }
  points.sort((a, b) => a.sequence - b.sequence)

  // Sites present in exactly one parameter — the symmetric difference of the key
  // sets. These are the rows a naive index pairing would silently mis-join.
  let missingN = 0
  for (const key of xByKey.keys()) if (!yByKey.has(key)) missingN++
  for (const key of yByKey.keys()) if (!xByKey.has(key)) missingN++

  return finalize('cd-cd', paramX, paramY, points, missingN, {
    sameMsrSequenceJoin: false,
    demoCoupled: false
  })
}

/**
 * Exact-pair join of a CD parameter against a per-sequence dynamic FDC channel of
 * the SAME MSR, keyed by sequence (dynamic_fdc is keyed by sequence string).
 * Sequences with a measured CD but no FDC value (or vice versa) are dropped and
 * counted as `missing`. Same-MSR + same-sequence join; demo-coupled on home mock.
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

  return finalize('cd-fdc', cdParam, fdcParam, points, missingN, {
    sameMsrSequenceJoin: true,
    demoCoupled: true
  })
}
