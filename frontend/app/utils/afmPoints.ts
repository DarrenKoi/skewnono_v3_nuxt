// Pure helpers for the AFM 측정 상세 point rail: which block a row belongs to, a
// point's state, where its site sits, which point an image shows. No DOM/Nuxt
// imports so they run under `node --test`.
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'

// Summary block names (the `Site` column), in payload order.
export const blockNames = (summary: AfmSummaryRow[]): string[] =>
  [...new Set(summary.map(row => row.Site))]

// A block has no key of its own — `Method_ID` repeats across every block of a
// file. Rows arrive block by block and a block holds a point at most once, so a
// point coming round again is where the next block starts. (Counting a point's
// own rows instead would misfile a point that an earlier block never measured.)
const blockOrdinals = (data: AfmDetailRow[]): number[] => {
  let block = 0
  let seen = new Set<string>()
  return data.map((row) => {
    if (seen.has(row.measurement_point)) {
      block += 1
      seen = new Set()
    }
    seen.add(row.measurement_point)
    return block
  })
}

// The name is the Summary block at the same ordinal. A block the measurement
// stopped in has rows but no Summary, and some files have no Summary at all:
// those get a numbered name.
const blockName = (names: string[], index: number) => names[index] ?? `Block ${index + 1}`

export interface PointBlock {
  name: string
  row: AfmDetailRow
}

export const blocksOfPoint = (data: AfmDetailRow[], summary: AfmSummaryRow[], point: string): PointBlock[] => {
  const names = blockNames(summary)
  const ordinals = blockOrdinals(data)
  return data.flatMap((row, i) =>
    row.measurement_point === point ? [{ name: blockName(names, ordinals[i]!), row }] : []
  )
}

// Rows with a `Block` column, added only where a file has more than one block:
// on a single-block file the column would repeat one name down the table.
export const tagBlocks = (data: AfmDetailRow[], summary: AfmSummaryRow[]): AfmDetailRow[] => {
  const names = blockNames(summary)
  const ordinals = blockOrdinals(data)
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

// The name every other file of a measurement starts with: its list file name
// without `.csv`, and without the `_Info` a MAPC01 list name carries.
export const measurementStem = (filename: string): string => filename.replace(/(_Info)?\.csv$/i, '')

// Which point an image file shows. An image is named `<stem>_<point>_<kind>`,
// and the point is read only after the stem: a recipe or lot that happens to
// contain `_0001_` must not claim the image, so a name that does not start with
// the stem has no point rather than a guessed one. A site-form key contains
// the plain point number, so the longest match wins.
export const imagePoint = (name: string, stem: string, points: string[]): string => {
  if (!name.startsWith(stem)) return ''
  const tail = name.slice(stem.length)
  return points
    .filter(point => tail.includes(`_${point}_`))
    .sort((a, b) => b.length - a.length)[0] ?? ''
}
