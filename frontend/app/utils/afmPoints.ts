// Pure helpers for the AFM 측정 상세 point rail: which block a row belongs to, a
// point's state, where its site sits, which point an image shows. No DOM/Nuxt
// imports so they run under `node --test`.
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'

// Summary block names (the `Site` column), in payload order.
export const blockNames = (summary: AfmSummaryRow[]): string[] =>
  [...new Set(summary.map(row => row.Site))]

// Every data row names its own block: `Site` holds the method name of the
// section the row came from — the name the Summary rows carry too (office 확인
// 2026-10-06). A block is never inferred from row order: a repeat recipe
// measures a point several times inside one block, and a stopped block has no
// row for the points it never reached. Rows with no `Site` are one block.
export const blockOf = (row: AfmDetailRow, fallback: string): string =>
  typeof row.Site === 'string' && row.Site !== '' ? row.Site : fallback

// The block of a row that names none.
export const fallbackBlock = (summary: AfmSummaryRow[]) => blockNames(summary)[0] ?? 'Block 1'

export interface PointBlock {
  name: string
  row: AfmDetailRow
}

// One entry per row of the point, so a point a repeat recipe measured twice in
// a block shows both readings.
export const blocksOfPoint = (data: AfmDetailRow[], summary: AfmSummaryRow[], point: string): PointBlock[] => {
  const fallback = fallbackBlock(summary)
  return data.flatMap(row => row.measurement_point === point ? [{ name: blockOf(row, fallback), row }] : [])
}

// Rows with a `Block` column, added only where a file has more than one block:
// on a single-block file the column would repeat one name down the table.
export const tagBlocks = (data: AfmDetailRow[], summary: AfmSummaryRow[]): AfmDetailRow[] => {
  const fallback = fallbackBlock(summary)
  const names = data.map(row => blockOf(row, fallback))
  if (new Set(names).size < 2) return data
  return data.map((row, i) => ({ ...row, Block: names[i]! }))
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

interface SiteDot {
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

// Which point an image file shows. A name ends `_<point>_<kind>.<ext>`, and the
// END is the only part that can be trusted: a MAPC01 image does not start with
// the measurement's list name (its fifth and sixth fields differ — office 확인
// 2026-10-06). Anchoring there also keeps a recipe or lot that happens to
// contain `_0001_` from claiming the image. A site-form key ends in the plain
// point number, so the longest match wins.
export const imagePoint = (name: string, points: string[]): string => {
  // A tip image's kind is the one that holds an underscore: `_<point>_C_PR`
  // (office 확인 2026-10-07).
  const stem = name.replace(/\.\w+$/, '').replace(/_C_PR$/, '_PR')
  const end = stem.lastIndexOf('_')
  if (end < 0) return ''
  const head = stem.slice(0, end)
  return points
    .filter(point => head.endsWith(`_${point}`))
    .sort((a, b) => b.length - a.length)[0] ?? ''
}
