// Physical wafer geometry shared by the wafer map and radius plot.
//
// The mock (and the office data it mirrors — docs/datatables/hitachi/msr_file_pickle.txt)
// keeps three coherent fields:
//   • chip_number      — die INDEX "(col,row)", centred on the wafer
//   • stage_coordinate — physical position "(x,y)" in nm, corner origin
//   • exe_detail_info  — all STRINGS, office-confirmed 2026-07-24:
//       chip_array  "26,33"              die array (cols,rows)
//       chip_pitch  "12520000,10340000"  die pitch in nm (x,y)
//       wafer_size  "300000000"          wafer diameter in nm (= 300 mm)
//       map_offset  "0,4610000"          die-grid offset in nm (x,y)
//       map_origin  "12,15"              ARRAY index of the origin die
// The wafer centre sits at (wafer_size/2, wafer_size/2) in nm, so a point's
// position relative to centre is (stage − centre). Everything below converts to
// millimetres so the plots read in real units.
import type { ExeDetailInfo } from '~/composables/useMsrFileApi'

const NM_PER_MM = 1_000_000

export interface WaferGeometry {
  sizeMm: number // wafer diameter (mm)
  radiusMm: number // wafer_size / 2
  centerNm: number // nm coordinate of the wafer centre (corner origin)
  pitchXmm: number // die pitch x (mm); 0 when unknown
  pitchYmm: number // die pitch y (mm); 0 when unknown
  // Die-grid offset (mm) from map_offset: the die array is shifted this far off
  // the wafer centre. Applies to DIE-INDEXED geometry only (die centres, grid
  // boundaries, die-index labels) — never to stagePosMm, whose origin is the
  // physical wafer centre that centre→edge effects reference.
  offsetXmm: number
  offsetYmm: number
  // map_origin — the ARRAY index of the origin die. chip_number is already
  // expressed relative to it, so this is informational and never enters the
  // placement math. Exposed so the office can verify the assumption.
  originCol: number
  originRow: number
}

const num = (s: string | undefined): number => {
  const n = Number(s)
  return Number.isFinite(n) ? n : NaN
}

// wafer_size arrives in nm from the office pickle ("300000000") but legacy
// fixtures/stored values said mm ("300"). Diameters are 100–450 mm, so any
// value ≥ 1000 must be nm — there is no wafer between 450 mm and 100 m.
const sizeToMm = (raw: number): number => (raw >= 1000 ? raw / NM_PER_MM : raw)

// "x,y" pair of numbers; each component falls back to 0 when absent/unparseable
// so a missing geometry field degrades to "no offset" rather than NaN.
const pairNm = (raw: string | undefined): [number, number] => {
  const [a, b] = (raw ?? '').split(',')
  const x = num(a)
  const y = num(b)
  return [Number.isFinite(x) ? x : 0, Number.isFinite(y) ? y : 0]
}

export const parseWaferGeometry = (info?: ExeDetailInfo | null): WaferGeometry => {
  const sizeRaw = num(info?.wafer_size)
  const sizeMm = sizeRaw > 0 ? sizeToMm(sizeRaw) : 300
  const [px, py] = (info?.chip_pitch ?? '').split(',')
  const pxNm = num(px)
  const pyNm = num(py)
  const [offXnm, offYnm] = pairNm(info?.map_offset)
  const [originCol, originRow] = pairNm(info?.map_origin)
  return {
    sizeMm,
    radiusMm: sizeMm / 2,
    centerNm: (sizeMm / 2) * NM_PER_MM,
    pitchXmm: pxNm > 0 ? pxNm / NM_PER_MM : 0,
    pitchYmm: pyNm > 0 ? pyNm / NM_PER_MM : 0,
    offsetXmm: offXnm / NM_PER_MM,
    offsetYmm: offYnm / NM_PER_MM,
    originCol,
    originRow
  }
}

// Physical position (mm, relative to wafer centre) from a stage_coordinate string.
export const stagePosMm = (stage: string, geo: WaferGeometry): [number, number] | null => {
  const parts = stage.split(',')
  if (parts.length !== 2) return null
  const x = num(parts[0])
  const y = num(parts[1])
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return [(x - geo.centerNm) / NM_PER_MM, (y - geo.centerNm) / NM_PER_MM]
}

// Die centre (mm, relative to the WAFER centre) from a chip_number "(col,row)".
// The die array is shifted off the wafer centre by map_offset, so a die centre
// is offset + col·pitch — this is what makes die tiles land on the measured
// points instead of sitting map_offset away from them.
export const dieCenterMm = (col: number, row: number, geo: WaferGeometry): [number, number] =>
  [geo.offsetXmm + col * geo.pitchXmm, geo.offsetYmm + row * geo.pitchYmm]

// Distance from wafer centre (mm) for a stage_coordinate — the radius-plot x.
export const siteRadiusMm = (stage: string, geo: WaferGeometry): number | null => {
  const p = stagePosMm(stage, geo)
  return p ? Math.hypot(p[0], p[1]) : null
}

// Convert a physical mm coordinate to its die-grid index (col or row). The grid
// is shifted by map_offset, so the offset is removed before dividing by pitch.
// Returns null when the pitch is unknown so callers can fall back to mm labels —
// never guess die 0.
export const mmToDieIndex = (mm: number, pitchMm: number, offsetMm = 0): number | null =>
  pitchMm > 0 ? Math.round((mm - offsetMm) / pitchMm) : null

// The die cell "(col,row)" a physical stage_coordinate falls in — the inverse of
// dieCenterMm. A measured point sits inside its die (offset < 0.5·pitch), so
// rounding recovers the die exactly. Format matches chip_number so the two are
// directly comparable.
//
// Returns null when the pitch is unknown or the coordinate is unparseable. The
// caller MUST treat null as "cannot place this point" — never as die (0,0),
// which would silently pile unplaceable points onto the wafer centre.
export const snapToDieCell = (stage: string, geo: WaferGeometry): string | null => {
  if (!(geo.pitchXmm > 0) || !(geo.pitchYmm > 0)) return null
  const pos = stagePosMm(stage, geo)
  if (!pos) return null
  const col = Math.round((pos[0] - geo.offsetXmm) / geo.pitchXmm)
  const row = Math.round((pos[1] - geo.offsetYmm) / geo.pitchYmm)
  return `${col},${row}`
}
