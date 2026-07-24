// Die-boundary grid for the wafer map, at TRUE die size.
//
// The msr file's exe_detail_info carries the die pitch (chip_pitch, nm), and
// die centres sit on integer multiples of it (chip_number (col,row) ↔
// col·pitch from the wafer centre — see waferGeometry.dieCenterMm). Die
// BOUNDARIES therefore run at (k + 0.5)·pitch. Each boundary line is clipped
// to its chord across the wafer circle so the grid reads as the wafer's real
// die layout, not a square mesh over the bounding box.
//
// Pure (geometry in, segments out) so it runs under raw `node --test`.
import type { WaferGeometry } from './waferGeometry.ts'

export type DieGridSegment = [start: [number, number], end: [number, number]]

// Safety valve: a corrupt pitch (µm misread as mm, etc.) could ask for
// thousands of lines; past this the "grid" would render as a solid sheet.
const MAX_LINES_PER_AXIS = 200

const round3 = (n: number): number => Number(n.toFixed(3))

// Boundary coordinates (k + 0.5)·pitch strictly inside (−radius, radius).
const boundaries = (pitch: number, radius: number): number[] => {
  if (!(pitch > 0) || !(radius > 0)) return []
  if (radius / pitch > MAX_LINES_PER_AXIS) return []
  const out: number[] = []
  const kMax = Math.ceil(radius / pitch)
  for (let k = -kMax - 1; k <= kMax; k++) {
    const c = (k + 0.5) * pitch
    if (Math.abs(c) < radius) out.push(c)
  }
  return out
}

export const buildDieGridSegments = (geo: WaferGeometry, radiusMm: number): DieGridSegment[] => {
  const segments: DieGridSegment[] = []
  for (const x of boundaries(geo.pitchXmm, radiusMm)) {
    const chord = Math.sqrt(radiusMm * radiusMm - x * x)
    segments.push([[round3(x), round3(-chord)], [round3(x), round3(chord)]])
  }
  for (const y of boundaries(geo.pitchYmm, radiusMm)) {
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
