// Builds the plotted point sets for the wafer map from raw MsrFileRows.
//
// Two views, DIFFERENT granularity — this is the crux of the Field/Die split:
//   • fieldPoints: ONE point per measured row, at its own stage position. A die
//     can hold several measurements (mock cycles dies as `(seq-1) % len(dies)`),
//     so this is the only view where each measurement point is individually
//     hoverable. n is always 1.
//   • diePoints: ONE point per die (chip_number), aggregated — value is the mean
//     of the die's measurements, positioned at the die-grid centre so tiles align
//     to the pitch. n is the measurement count; seqs holds every sequence on the die.
//   • failurePoints: unmeasured rows (cd_value null) at their physical position.
//
// Kept pure (rows + geo in, plain data out) so the risky aggregation/positioning
// logic is unit-tested without mounting the chart. Rows should be pre-filtered to
// a single parameter by the caller.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow, measuredRows } from './msrRows.ts'
import { parseChipXY } from './waferChip.ts'
import { stagePosMm, dieCenterMm, type WaferGeometry } from './waferGeometry.ts'

// One plotted point. seqs drives outlier/focus ring matching; for a field point
// it is just [seq], for a die it is every sequence measured on that die.
export interface WaferPoint {
  seq: number
  field: string // chip_number ("col,row")
  mp: number // representative mp_number
  n: number // measurements folded into this point (1 for field points)
  seqs: number[]
  x: number // mm from wafer centre
  y: number
  value: number // cd_value (mean for a die)
}

export interface WaferFailure {
  seq: number
  x: number
  y: number
}

export interface WaferPoints {
  fieldPoints: WaferPoint[]
  diePoints: WaferPoint[]
  failurePoints: WaferFailure[]
}

const round3 = (n: number): number => Number(n.toFixed(3))

export const buildWaferPoints = (rows: MsrFileRow[], geo: WaferGeometry): WaferPoints => {
  const fieldPoints: WaferPoint[] = []

  // Die accumulator: sum/count for the mean, grid index for the tile centre,
  // and the full sequence set for ring lookups.
  interface DieAcc { col: number, row: number, sum: number, n: number, seq: number, mp: number, seqs: number[] }
  const dieAcc = new Map<string, DieAcc>()

  for (const r of measuredRows(rows)) {
    const chip = parseChipXY(r.chip_number)
    const pos = stagePosMm(r.stage_coordinate, geo)
    if (!chip || !pos) continue

    fieldPoints.push({
      seq: r.sequence,
      field: r.chip_number,
      mp: r.mp_number,
      n: 1,
      seqs: [r.sequence],
      x: pos[0],
      y: pos[1],
      value: round3(r.cd_value)
    })

    const e = dieAcc.get(r.chip_number)
      ?? { col: chip[0], row: chip[1], sum: 0, n: 0, seq: r.sequence, mp: r.mp_number, seqs: [] }
    e.sum += r.cd_value
    e.n += 1
    e.seqs.push(r.sequence)
    dieAcc.set(r.chip_number, e)
  }

  const diePoints: WaferPoint[] = [...dieAcc.entries()].map(([field, e]) => {
    const [cx, cy] = dieCenterMm(e.col, e.row, geo)
    return {
      seq: e.seq,
      field,
      mp: e.mp,
      n: e.n,
      seqs: e.seqs,
      x: cx,
      y: cy,
      value: round3(e.sum / e.n)
    }
  })

  const failurePoints: WaferFailure[] = []
  for (const r of rows) {
    if (isMeasuredRow(r)) continue
    const pos = stagePosMm(r.stage_coordinate, geo)
    if (!pos) continue
    failurePoints.push({ seq: r.sequence, x: pos[0], y: pos[1] })
  }

  return { fieldPoints, diePoints, failurePoints }
}
