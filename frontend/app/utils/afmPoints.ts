// Pure helpers for the AFM 측정 상세 point rail: which block a row belongs to, a
// point's state, where its site sits, which point an image shows. No DOM/Nuxt
// imports so they run under `node --test`.
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'

// Summary block names (the `Site` column), in payload order.
export const blockNames = (summary: AfmSummaryRow[]): string[] =>
  [...new Set(summary.map(row => row.Site))]

// A block has no key of its own — `Method_ID` repeats across every block of a
// file — so a row's block is its ordinal among the rows of its point, and the
// name is the Summary block at that ordinal. A block the measurement stopped in
// has rows but no Summary, and some files have no Summary at all: those get a
// numbered name.
const blockName = (names: string[], index: number) => names[index] ?? `Block ${index + 1}`

export interface PointBlock {
  name: string
  row: AfmDetailRow
}

export const blocksOfPoint = (data: AfmDetailRow[], summary: AfmSummaryRow[], point: string): PointBlock[] => {
  const names = blockNames(summary)
  return data
    .filter(row => row.measurement_point === point)
    .map((row, index) => ({ name: blockName(names, index), row }))
}

// Rows with a `Block` column, added only where a file has more than one block:
// on a single-block file the column would repeat one name down the table.
export const tagBlocks = (data: AfmDetailRow[], summary: AfmSummaryRow[]): AfmDetailRow[] => {
  const names = blockNames(summary)
  const seen = new Map<string, number>()
  const ordinals = data.map((row) => {
    const index = seen.get(row.measurement_point) ?? 0
    seen.set(row.measurement_point, index + 1)
    return index
  })
  if (!ordinals.some(index => index > 0)) return data
  return data.map((row, i) => ({ ...row, Block: blockName(names, ordinals[i]!) }))
}

// One state for a point that has a row per block: the worst one wins.
export const pointState = (rows: AfmDetailRow[]): string | null => {
  const states = rows.map(row => row.State)
  return states.find(s => s === 'FAILED') ?? states.find(s => s === 'STOPPED') ?? states[0] ?? null
}

// COMPLETED · FAILED · STOPPED are the three states a tool writes. The dot is
// never the only carrier: the rail prints a legend, the table the word.
export const STATE_DOT: Record<string, string> = {
  COMPLETED: 'bg-(--sk-ok)',
  FAILED: 'bg-(--sk-bad)',
  STOPPED: 'bg-(--sk-warn)'
}
export const STATE_BADGE: Record<string, 'success' | 'error' | 'warning'> = {
  COMPLETED: 'success',
  FAILED: 'error',
  STOPPED: 'warning'
}

export interface SiteDot {
  siteId: string
  // The first point measured at the site — what clicking the dot selects.
  point: string
  // Position inside the map, in percent. Y grows upwards on a wafer map.
  left: number
  top: number
}

// Only a recipe that records Site ID has `Site X` / `Site Y`; every other
// recipe returns no dots and the rail shows its list alone.
export const siteDots = (data: AfmDetailRow[]): SiteDot[] => {
  const sites = new Map<string, { x: number, y: number, point: string }>()
  for (const row of data) {
    const id = row['Site ID']
    const x = row['Site X']
    const y = row['Site Y']
    if (id == null || typeof x !== 'number' || typeof y !== 'number') continue
    if (!sites.has(String(id))) sites.set(String(id), { x, y, point: row.measurement_point })
  }
  const all = [...sites.values()]
  const spanX = Math.max(1, ...all.map(site => Math.abs(site.x)))
  const spanY = Math.max(1, ...all.map(site => Math.abs(site.y)))
  return [...sites].map(([siteId, site]) => ({
    siteId,
    point: site.point,
    left: 50 + (site.x / spanX) * 40,
    top: 50 - (site.y / spanY) * 36
  }))
}

// Which point an image file shows. An image is named after its measurement
// (`stem`, the data file name without `.csv`) followed by `_<point>_<kind>`, so
// the point is looked for after the stem — a lot or a time that happens to
// contain `_0001_` must not claim the image. A site-form key contains the
// plain point number, so the longest match wins.
export const imagePoint = (name: string, stem: string, points: string[]): string => {
  const tail = name.startsWith(stem) ? name.slice(stem.length) : name
  return points
    .filter(point => tail.includes(`_${point}_`))
    .sort((a, b) => b.length - a.length)[0] ?? ''
}

// "+1.23" / "−1.23": a difference always shows its sign.
export const formatDelta = (value: number): string =>
  `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(2)}`
