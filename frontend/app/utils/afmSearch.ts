// Pure filters for the AFM 측정 검색 list. No DOM/Nuxt imports so they run
// under `node --test`.
import type { AfmMeasurement } from '~/composables/useAfmCart'

export interface AfmSearchFilters {
  // Free text: every term must match somewhere in the row.
  terms: string[]
  // Empty = every recipe.
  recipes: string[]
  lot: string
  // How many days to keep, counted back from the newest measurement. null = all.
  days: number | null
}

// formattedDate is "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS".
const dayOf = (row: AfmMeasurement) => row.formattedDate.slice(0, 10)

const matchesTerm = (row: AfmMeasurement, term: string) =>
  [row.filename, row.recipeName, row.lotId, row.formattedDate, String(row.slotNumber), row.measuredInfo]
    .some(value => value.toLowerCase().includes(term))

// The days a 기간 preset keeps, as [from, to] day strings. The window ends at
// the newest measurement in the list rather than at today: a tool that has not
// measured since Friday still answers "1일" with Friday's lots, and the range
// is shown beside the presets so the anchor is never a guess.
export const dateWindow = (rows: AfmMeasurement[], days: number | null): [string, string] | null => {
  if (!rows.length) return null
  const sorted = rows.map(dayOf).sort()
  const to = sorted[sorted.length - 1]!
  if (!days) return [sorted[0]!, to]
  const from = new Date(`${to}T00:00:00Z`)
  from.setUTCDate(from.getUTCDate() - (days - 1))
  return [from.toISOString().slice(0, 10), to]
}

export const filterMeasurements = (rows: AfmMeasurement[], filters: AfmSearchFilters): AfmMeasurement[] => {
  const terms = filters.terms.map(t => t.toLowerCase().trim()).filter(Boolean)
  const lot = filters.lot.trim().toLowerCase()
  const from = dateWindow(rows, filters.days)?.[0] ?? ''
  return rows.filter(row =>
    (!filters.recipes.length || filters.recipes.includes(row.recipeName))
    && (!lot || row.lotId.toLowerCase().includes(lot))
    && dayOf(row) >= from
    && terms.every(term => matchesTerm(row, term))
  )
}
