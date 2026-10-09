// Pure helpers for 시계열 비교's 1D 프로파일 겹쳐 보기: which profiles of one point
// can share a chart, and the one optional correction (직선 제거). No DOM/Nuxt
// imports so they run under `node --test`. Nothing here converts a unit,
// resamples onto another profile's X, or shifts a profile along X.
import type { AfmProfileResponse } from '~/composables/useAfmDetailApi'
import { isLineProfile, measuredPoints, unitSymbol } from './afmHeatmap.ts'

export interface LineProfile {
  // As the file states them; never converted.
  xUnit: string
  zUnit: string
  // [x, z] of every sample that carries a height, in file order.
  data: [number, number][]
  // The server sent fewer samples than the file holds.
  thinned: boolean
}

// Why a profile is not on the chart. `none`: no profile for this point (or one
// with no height in it); `grid`: a 2D scan; `nounit`: the file states no unit;
// `failed`: the request failed; `unit`: its unit is not the chart's;
// `unchecked`: never requested.
export type ProfileSkip = 'none' | 'grid' | 'nounit' | 'failed' | 'unit' | 'unchecked'

export type ProfileLoad = { line: LineProfile } | { skip: ProfileSkip }

// What one profile response is to the overlay. 1D versus 2D is the detail
// page's own rule (isLineProfile: the file's DataSize, else one shared y).
export const readProfile = (res: Pick<AfmProfileResponse, 'data' | 'meta' | 'count' | 'total'>): ProfileLoad => {
  const measured = measuredPoints(res.data ?? [])
  if (!measured.length) return { skip: 'none' }
  if (!isLineProfile(res.data, res.meta?.data_size)) return { skip: 'grid' }
  const xUnit = res.meta?.x_unit
  const zUnit = res.meta?.z_unit
  if (!xUnit || !zUnit) return { skip: 'nounit' }
  return { line: { xUnit, zUnit, data: measured.map(p => [p.x, p.z]), thinned: (res.total ?? res.count) > res.count } }
}

// 직선 제거: the profile minus the least-squares line fitted to that profile's
// own samples. X is untouched. With no spread in x there is no slope to fit,
// so only the mean height is removed.
export const levelLine = (data: [number, number][]): [number, number][] => {
  const n = data.length
  if (!n) return []
  let sx = 0
  let sz = 0
  for (const [x, z] of data) {
    sx += x
    sz += z
  }
  const mx = sx / n
  const mz = sz / n
  let sxx = 0
  let sxz = 0
  for (const [x, z] of data) {
    sxx += (x - mx) ** 2
    sxz += (x - mx) * (z - mz)
  }
  const slope = sxx ? sxz / sxx : 0
  return data.map(([x, z]) => [x, z - mz - slope * (x - mx)])
}

export interface ProfileOverlay {
  // The one unit pair every drawn profile states; null when nothing is drawn.
  unit: { x: string, z: string } | null
  drawn: { key: string, line: LineProfile }[]
  skipped: { key: string, reason: ProfileSkip }[]
}

// The profiles that share one chart: 1D lines stating the same X and Z unit as
// the selected measurement's (else as the first line's, in the given order).
// Everything else is returned with its reason, in the given order.
export const overlayProfiles = (items: { key: string, load: ProfileLoad }[], selected: string | null): ProfileOverlay => {
  const lines = items.flatMap(({ key, load }) => 'line' in load ? [{ key, line: load.line }] : [])
  const ref = (lines.find(l => l.key === selected) ?? lines[0])?.line
  const same = (line: LineProfile) =>
    !!ref && unitSymbol(line.xUnit) === unitSymbol(ref.xUnit) && unitSymbol(line.zUnit) === unitSymbol(ref.zUnit)
  return {
    unit: ref ? { x: ref.xUnit, z: ref.zUnit } : null,
    drawn: lines.filter(l => same(l.line)),
    skipped: items.flatMap(({ key, load }): ProfileOverlay['skipped'] =>
      'skip' in load ? [{ key, reason: load.skip }] : same(load.line) ? [] : [{ key, reason: 'unit' }])
  }
}
