// Pure logic for the AFM 측정 검색 list: turning a backend row into the row the
// pages use, and filtering the list. No DOM/Nuxt imports so it runs under
// `node --test`.
import { shiftIsoDate } from './dateTime.ts'
import type { AfmMeasurement } from '~/composables/useAfmCart'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'

// Backend rows carry the measurement time as a raw HHMMSS code separate from
// formatted_date; fold it into the display date so lists show
// "YYYY-MM-DD HH:MM:SS". A row with no date stays '' rather than a bare time.
export const measuredAt = (row: AfmFileRow): string => {
  const day = row.formatted_date ?? ''
  // The measurement's own start where the list has it: `time` is the session's
  // on MAP608, shared by every measurement of the session.
  const code = row.measured_time ?? row.time ?? ''
  if (!day || !/^\d{4,6}$/.test(code)) return day
  const padded = code.padEnd(6, '0')
  return `${day} ${padded.slice(0, 2)}:${padded.slice(2, 4)}:${padded.slice(4, 6)}`
}

// The one place a backend list row becomes an AfmMeasurement. The row type
// says every text cell is a string, but nobody has seen an office response at
// home: a missing cell becomes '' here, so the list, the cart and 시계열 비교
// never meet a null.
export const toMeasurement = (row: AfmFileRow): AfmMeasurement => ({
  filename: row.filename,
  recipeName: row.recipe_name ?? '',
  lotId: row.lot_id ?? '',
  slotNumber: row.slot_number ?? '',
  measuredInfo: row.measured_info ?? '',
  formattedDate: measuredAt(row),
  hasProfile: row.has_profile,
  hasData: row.has_data,
  hasImage: row.has_image,
  hasAlign: row.has_align,
  hasTip: row.has_tip
})

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

// formattedDate is "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"; '' when unknown.
const dayOf = (row: AfmMeasurement) => row.formattedDate.slice(0, 10)

const matchesTerm = (row: AfmMeasurement, term: string) =>
  [row.filename, row.recipeName, row.lotId, row.formattedDate, String(row.slotNumber), row.measuredInfo]
    .some(value => value.toLowerCase().includes(term))

// The first day a 기간 preset keeps: the last `days` days ending today, so
// "오늘" on a tool that has not measured today is empty rather than quietly
// showing an older day.
const windowStart = (today: string, days: number) => shiftIsoDate(today, days - 1)

// What the range label shows, as [from, to] day strings: the preset's window,
// or with no preset the span of the dated rows in the list.
export const dateWindow = (rows: AfmMeasurement[], days: number | null, today: string): [string, string] | null => {
  if (days) return [windowStart(today, days), today]
  const sorted = rows.map(dayOf).filter(Boolean).sort()
  if (!sorted.length) return null
  return [sorted[0]!, sorted[sorted.length - 1]!]
}

// A row with no date stays in 전체 and leaves every dated window.
export const filterMeasurements = (rows: AfmMeasurement[], filters: AfmSearchFilters): AfmMeasurement[] => {
  const terms = filters.terms.map(t => t.toLowerCase().trim()).filter(Boolean)
  const lot = filters.lot.trim().toLowerCase()
  const from = filters.days ? windowStart(filters.today, filters.days) : ''
  return rows.filter(row =>
    (!filters.recipes.length || filters.recipes.includes(row.recipeName))
    && (!lot || row.lotId.toLowerCase().includes(lot))
    && dayOf(row) >= from
    && terms.every(term => matchesTerm(row, term))
  )
}
