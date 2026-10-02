// Pure filters for the AFM 측정 검색 list. No DOM/Nuxt imports so they run
// under `node --test`.
import type { AfmMeasurement } from '~/composables/useAfmCart'

export interface AfmSearchFilters {
  // Free text: every term must match somewhere in the row.
  terms: string[]
  // Empty = every recipe.
  recipes: string[]
  lot: string
  // How many days to keep, counted back from `today` inclusive. null = all.
  days: number | null
  // The viewer's local date, "YYYY-MM-DD".
  today: string
}

// The list is typed as all strings, but it is built from an office response
// nobody has seen at home: a missing cell reads as empty here instead of
// throwing, so one odd row cannot take the whole list down.
const text = (value: unknown) => String(value ?? '').toLowerCase()

// formattedDate is "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"; '' when unknown.
const dayOf = (row: AfmMeasurement) => String(row.formattedDate ?? '').slice(0, 10)

const matchesTerm = (row: AfmMeasurement, term: string) =>
  [row.filename, row.recipeName, row.lotId, row.formattedDate, row.slotNumber, row.measuredInfo]
    .some(value => text(value).includes(term))

// The days a 기간 preset keeps, as [from, to] day strings: the last `days` days
// ending today, so "오늘" on a tool that has not measured today is empty rather
// than quietly showing an older day. With no preset it is the span of the list.
export const dateWindow = (rows: AfmMeasurement[], days: number | null, today: string): [string, string] | null => {
  if (days) {
    const from = new Date(`${today}T00:00:00Z`)
    from.setUTCDate(from.getUTCDate() - (days - 1))
    return [from.toISOString().slice(0, 10), today]
  }
  const sorted = rows.map(dayOf).filter(Boolean).sort()
  if (!sorted.length) return null
  return [sorted[0]!, sorted[sorted.length - 1]!]
}

export const filterMeasurements = (rows: AfmMeasurement[], filters: AfmSearchFilters): AfmMeasurement[] => {
  const terms = filters.terms.map(t => t.toLowerCase().trim()).filter(Boolean)
  const lot = filters.lot.trim().toLowerCase()
  const from = filters.days ? dateWindow(rows, filters.days, filters.today)![0] : ''
  return rows.filter(row =>
    (!filters.recipes.length || filters.recipes.includes(row.recipeName))
    && (!lot || text(row.lotId).includes(lot))
    && dayOf(row) >= from
    && terms.every(term => matchesTerm(row, term))
  )
}
