// Pure helpers for 측정 상세's Site 격자: one measured column laid out on the
// rows' `Site X` / `Site Y`. Those are unitless integer indices. The larger
// Site Y is drawn at the top (user-confirmed 2026-10-09). The notch position
// cannot be known (user-confirmed the same day: the raw files carry no wafer
// orientation), and the X direction and any mapping to wafer mm are not
// confirmed — so this is an index layout only: no notch, no radius, no
// centre/edge, no mm.
// No DOM/Nuxt imports so it runs under `node --test`.
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { blockOf, fallbackBlock, pointState } from './afmPoints.ts'
import { summaryNumber } from './afmSummary.ts'
import { isValidRow } from './afmTrend.ts'
import { mean } from './stats.ts'

export interface SiteCell {
  x: number
  y: number
  // The points measured at this site, in row order. One site can hold several
  // (up to 14 seen), so a cell is not a point.
  points: string[]
  // Mean of the points that gave a value; null when none did. Never built from
  // a FAILED, STOPPED or Valid FALSE reading.
  value: number | null
  valued: number
  // The most rows one point has here: 2 on a recipe that goes round twice.
  laps: number
  // The worst state among the points' readings (FAILED, then STOPPED).
  state: string | null
  // Points whose reading is not a value: not `isValidRow`, or no number.
  invalid: number
}

export interface SiteGrid {
  // Every index from the smallest to the largest seen, so a gap stays a gap.
  xs: number[]
  ys: number[]
  cells: SiteCell[]
  min: number | null
  max: number | null
}

const span = (values: number[]): number[] => {
  if (!values.length) return []
  const from = Math.min(...values)
  return Array.from({ length: Math.max(...values) - from + 1 }, (_, i) => from + i)
}

const siteIndex = (raw: unknown): number | null => {
  const n = summaryNumber(raw)
  return n !== null && Number.isInteger(n) ? n : null
}

// Rows by the block they name (`Site`), in first-appearance order.
export const blockRows = (data: AfmDetailRow[], summary: AfmSummaryRow[]): Map<string, AfmDetailRow[]> => {
  const fallback = fallbackBlock(summary)
  const blocks = new Map<string, AfmDetailRow[]>()
  for (const row of data) {
    const name = blockOf(row, fallback)
    const list = blocks.get(name)
    if (list) list.push(row)
    else blocks.set(name, [row])
  }
  return blocks
}

// One block's rows as cells. A point's reading is its LAST row — the rule
// `measurementStats` has for a repeat recipe's laps (a later lap replaces the
// earlier one) — and the cell says how many laps there were.
export const siteGrid = (rows: AfmDetailRow[], column: string): SiteGrid => {
  const sites = new Map<string, { x: number, y: number, last: Map<string, AfmDetailRow>, laps: Map<string, number> }>()
  for (const row of rows) {
    const x = siteIndex(row['Site X'])
    const y = siteIndex(row['Site Y'])
    if (x === null || y === null) continue
    const key = `${x},${y}`
    const site = sites.get(key) ?? { x, y, last: new Map(), laps: new Map() }
    sites.set(key, site)
    site.last.set(row.measurement_point, row)
    site.laps.set(row.measurement_point, (site.laps.get(row.measurement_point) ?? 0) + 1)
  }
  const cells = [...sites.values()].map(({ x, y, last, laps }): SiteCell => {
    const readings = [...last.values()]
    const values = readings.flatMap((row) => {
      const value = isValidRow(row) ? summaryNumber(row[column]) : null
      return value === null ? [] : [value]
    })
    return {
      x,
      y,
      points: [...last.keys()],
      value: values.length ? mean(values) : null,
      valued: values.length,
      laps: Math.max(...laps.values()),
      state: pointState(readings),
      invalid: readings.length - values.length
    }
  })
  const values = cells.flatMap(cell => cell.value === null ? [] : [cell.value])
  return {
    xs: span(cells.map(cell => cell.x)),
    ys: span(cells.map(cell => cell.y)),
    cells,
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null
  }
}
