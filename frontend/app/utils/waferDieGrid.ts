// Die-boundary grid for the wafer map, at TRUE die size.
//
// The msr file's exe_detail_info carries the die pitch (chip_pitch, nm), and
// die centres sit on the offset die grid (chip_number (col,row) ↔
// map_offset + col·pitch from the wafer centre — see waferGeometry.dieCenterMm).
// Die BOUNDARIES therefore run at map_offset + (k + 0.5)·pitch. Each boundary
// line is clipped to its chord across the wafer circle so the grid reads as the
// wafer's real die layout, not a square mesh over the bounding box.
//
// Pure (geometry in, segments out) so it runs under raw `node --test`.
import type { WaferGeometry } from './waferGeometry.ts'

export type DieGridSegment = [start: [number, number], end: [number, number]]

// Safety valve: a corrupt pitch (µm misread as mm, etc.) could ask for
// thousands of lines; past this the "grid" would render as a solid sheet.
const MAX_LINES_PER_AXIS = 200

const round3 = (n: number): number => Number(n.toFixed(3))

// Lattice coordinates offset + (k + phase)·pitch strictly inside (−limit, limit).
// The die array is shifted off the wafer centre by map_offset, so the lattice is
// measured from the shifted grid — otherwise the lines sit map_offset away from
// the points they are supposed to enclose.
//
// `phase` picks which lattice: 0 = die centres, 0.5 = the boundaries between
// them. Both come from here on purpose. They are drawn by different ECharts
// mechanisms — a line series and the axis ticks — and while each derived its own
// positions they ended up on different grids and the map drew two of them.
const lattice = (pitch: number, limit: number, offset: number, phase: number): number[] => {
  if (!(pitch > 0) || !(limit > 0)) return []
  if (limit / pitch > MAX_LINES_PER_AXIS) return []
  const out: number[] = []
  // One extra ring beyond the limit covers any |offset| < pitch, so a shifted
  // grid cannot clip its outermost line off either edge.
  const kMax = Math.ceil(limit / pitch) + 1
  for (let k = -kMax; k <= kMax; k++) {
    const c = offset + (k + phase) * pitch
    if (Math.abs(c) < limit) out.push(round3(c))
  }
  return out
}

const boundaries = (pitch: number, radius: number, offset: number): number[] =>
  lattice(pitch, radius, offset, 0.5)

// Die-centre coordinates, for the axis ticks that number the bands those
// boundaries enclose. `limit` is the axis extent rather than the wafer radius:
// an edge die whose centre falls just off the wafer still owns a visible band,
// and ECharts clips custom tick values to the axis range regardless.
export const dieCentreTicks = (pitchMm: number, limitMm: number, offsetMm: number): number[] =>
  lattice(pitchMm, limitMm, offsetMm, 0)

export const buildDieGridSegments = (geo: WaferGeometry, radiusMm: number): DieGridSegment[] => {
  const segments: DieGridSegment[] = []
  for (const x of boundaries(geo.pitchXmm, radiusMm, geo.offsetXmm)) {
    const chord = Math.sqrt(radiusMm * radiusMm - x * x)
    segments.push([[round3(x), round3(-chord)], [round3(x), round3(chord)]])
  }
  for (const y of boundaries(geo.pitchYmm, radiusMm, geo.offsetYmm)) {
    const chord = Math.sqrt(radiusMm * radiusMm - y * y)
    segments.push([[round3(-chord), round3(y)], [round3(chord), round3(y)]])
  }
  return segments
}

// Flattened for a single ECharts line series: segments separated by a null
// point so one series draws the whole grid without connecting across gaps.
export const dieGridLineData = (geo: WaferGeometry, radiusMm: number): ([number, number] | [null, null])[] => {
  const data: ([number, number] | [null, null])[] = []
  for (const [start, end] of buildDieGridSegments(geo, radiusMm)) {
    data.push(start, end, [null, null])
  }
  return data
}
