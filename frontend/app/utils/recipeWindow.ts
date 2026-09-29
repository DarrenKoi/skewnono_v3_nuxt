import type { MeasHistRow } from '~/composables/useMeasHistApi'
import { formatDateTimeInput } from './dateTime.ts'

// Pure: the measurements around one hardware timestamp, as the recipe-window
// popup lists them. Both sides are KST wall clock: hardware timestamps are
// offset-less, meas_hist rows carry it with a Z tag, so the Z is dropped
// rather than read as UTC (reading it would put every row 9 h away).

// A failed-image share this high marks a problem row. It follows the problem
// band of docs/datatables/hitachi/meas_hist.txt rule 9 (15-80 %); whether the
// office sees the same split is OFFICE-VERIFY.
export const RECIPE_WINDOW_FAIL_RATIO = 15

export type RecipeWindowFlag = 'align' | 'msr' | 'images'

export interface RecipeWindowRow {
  row: MeasHistRow
  /** Minutes from the clicked time to the measurement's timestamp. */
  offsetMin: number
  flags: RecipeWindowFlag[]
}

const wallEpoch = (value: string): number => new Date(value.replace('Z', '').replace(' ', 'T')).getTime()

const flagsOf = (row: MeasHistRow): RecipeWindowFlag[] => [
  ...(row.align_fail === 'Fail' ? ['align' as const] : []),
  ...(row.msr_check === 'No' ? ['msr' as const] : []),
  ...(row.fail_ratio >= RECIPE_WINDOW_FAIL_RATIO ? ['images' as const] : [])
]

export const recipeWindowRows = (rows: MeasHistRow[], at: string): RecipeWindowRow[] => {
  const atEpoch = wallEpoch(at)
  // Sorted on the exact distance; only the displayed minutes are rounded.
  return rows
    .map(row => ({ row, ms: wallEpoch(row.timestamp) - atEpoch }))
    .sort((a, b) => Math.abs(a.ms) - Math.abs(b.ms) || a.ms - b.ms)
    .map(({ row, ms }) => ({ row, offsetMin: Math.round(ms / 60_000), flags: flagsOf(row) }))
}

export const recipeWindowSummary = (rows: RecipeWindowRow[]) => ({
  total: rows.length,
  recipes: new Set(rows.map(r => r.row.full_name)).size,
  align: rows.filter(r => r.flags.includes('align')).length,
  msr: rows.filter(r => r.flags.includes('msr')).length,
  images: rows.filter(r => r.flags.includes('images')).length
})

/** An epoch read off a chart's time axis, back to the offset-less wall clock
 * it was parsed from (the browser's local zone, KST at the office). */
export const wallClockIso = (epoch: number): string => {
  const d = new Date(epoch)
  return `${formatDateTimeInput(d)}:${String(d.getSeconds()).padStart(2, '0')}`
}
