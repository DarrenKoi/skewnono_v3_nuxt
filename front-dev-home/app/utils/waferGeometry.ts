// Physical wafer geometry shared by the wafer map and radius plot.
//
// The mock (and the office data it mirrors — docs/datatables/msr_file_pickle.txt)
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
}

const num = (s: string | undefined): number => {
  const n = Number(s)
  return Number.isFinite(n) ? n : NaN
}

// wafer_size arrives in nm from the office pickle ("300000000") but legacy
// fixtures/stored values said mm ("300"). Diameters are 100–450 mm, so any
// value ≥ 1000 must be nm — there is no wafer between 450 mm and 100 m.
const sizeToMm = (raw: number): number => (raw >= 1000 ? raw / NM_PER_MM : raw)

export const parseWaferGeometry = (info?: ExeDetailInfo | null): WaferGeometry => {
  const sizeRaw = num(info?.wafer_size)
  const sizeMm = sizeRaw > 0 ? sizeToMm(sizeRaw) : 300
  const [px, py] = (info?.chip_pitch ?? '').split(',')
  const pxNm = num(px)
  const pyNm = num(py)
  return {
    sizeMm,
    radiusMm: sizeMm / 2,
    centerNm: (sizeMm / 2) * NM_PER_MM,
    pitchXmm: pxNm > 0 ? pxNm / NM_PER_MM : 0,
    pitchYmm: pyNm > 0 ? pyNm / NM_PER_MM : 0
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

// Die centre (mm, relative to wafer centre) from a chip_number "(col,row)". Uses
// the pitch, so tiles land on the die grid regardless of the measured offset.
export const dieCenterMm = (col: number, row: number, geo: WaferGeometry): [number, number] =>
  [col * geo.pitchXmm, row * geo.pitchYmm]

// Distance from wafer centre (mm) for a stage_coordinate — the radius-plot x.
export const siteRadiusMm = (stage: string, geo: WaferGeometry): number | null => {
  const p = stagePosMm(stage, geo)
  return p ? Math.hypot(p[0], p[1]) : null
}

// Convert a physical mm coordinate to its die-grid index (col or row). Returns
// null when the pitch is unknown so callers can fall back to mm labels.
export const mmToDieIndex = (mm: number, pitchMm: number): number | null =>
  pitchMm > 0 ? Math.round(mm / pitchMm) : null
