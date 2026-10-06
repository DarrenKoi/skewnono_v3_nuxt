// Pure logic for AFM 가동 현황: one tool's measurement list, read along time —
// how much it measured each day, at which hours, and where measurements failed.
// No DOM/Nuxt imports so it runs under `node --test`. A day is `formatted_date`
// and an hour the head of the `time` code, as text: nothing here goes through
// `Date`, so no timezone can move a measurement to another day.
import { inclusiveDayCount, shiftIsoDate } from './dateTime.ts'
import { dateWindow, toMeasurement } from './afmSearch.ts'
import type { AfmFileRow } from '~/composables/useAfmDetailApi'

export interface UsageRow {
  // The backend row, for opening the measurement.
  row: AfmFileRow
  // null: the measurement belongs to no day.
  day: string | null
  // 0–23; null where the list has no usable `time`.
  hour: number | null
  // "HH:MM:SS", '' with no usable `time`.
  clock: string
  // '' where the list names none.
  recipe: string
  lot: string
  points: number | null
  notCompleted: number | null
  invalid: number | null
}

// The office writes a missing time as null or `NA`; a tool writes HHMM or HHMMSS.
const clockOf = (time: string | null | undefined): string => {
  if (!time || !/^\d{4,6}$/.test(time)) return ''
  const code = time.padEnd(6, '0')
  return Number(code.slice(0, 2)) > 23 ? '' : `${code.slice(0, 2)}:${code.slice(2, 4)}:${code.slice(4, 6)}`
}

export const hourOf = (time: string | null | undefined): number | null => {
  const clock = clockOf(time)
  return clock ? Number(clock.slice(0, 2)) : null
}

export const usageRows = (rows: AfmFileRow[]): UsageRow[] =>
  rows.map(row => ({
    row,
    day: (row.formatted_date ?? '').slice(0, 10) || null,
    hour: hourOf(row.time),
    clock: clockOf(row.time),
    recipe: row.recipe_name ?? '',
    lot: row.lot_id ?? '',
    points: row.point_count ?? null,
    notCompleted: row.not_completed_count ?? null,
    invalid: row.invalid_count ?? null
  }))

// [first day, last day] of a 기간: the search page's own window (the last N
// days ending today), or with no preset the span of the dated measurements.
export const usageWindow = (rows: AfmFileRow[], days: number | null, today: string): [string, string] | null =>
  dateWindow(rows.map(toMeasurement), days, today)

// Every calendar day of a window, oldest first — idle days included.
export const usageDays = ([from, to]: [string, string]): string[] => {
  const n = inclusiveDayCount(from, to)
  return Array.from({ length: n }, (_, i) => shiftIsoDate(to, n - 1 - i))
}

// A measurement with no day is in no window.
export const inWindow = (rows: UsageRow[], [from, to]: [string, string]): UsageRow[] =>
  rows.filter(r => r.day !== null && r.day >= from && r.day <= to)

export interface UsageSummary {
  count: number
  activeDays: number
  // null with no active day: there is nothing to average over.
  perActiveDay: number | null
  recipes: number
  lots: number
  // Summed over the measurements that have a count; the rest are `pointsMissing`.
  points: number
  pointsMissing: number
  // `known` measurements carry the value, `hit` of them have it above zero.
  notCompleted: { hit: number, known: number }
}

export const usageSummary = (rows: UsageRow[]): UsageSummary => {
  const activeDays = new Set(rows.map(r => r.day)).size
  const counted = rows.filter(r => r.points !== null)
  const judged = rows.filter(r => r.notCompleted !== null)
  return {
    count: rows.length,
    activeDays,
    perActiveDay: activeDays ? rows.length / activeDays : null,
    recipes: new Set(rows.map(r => r.recipe).filter(Boolean)).size,
    lots: new Set(rows.map(r => r.lot).filter(Boolean)).size,
    points: counted.reduce((sum, r) => sum + r.points!, 0),
    pointsMissing: rows.length - counted.length,
    notCompleted: { hit: judged.filter(r => r.notCompleted! > 0).length, known: judged.length }
  }
}

export interface DaySeries {
  name: string
  // One count per day of the window.
  values: number[]
}

// Reads 기타. The zero-width space keeps the bucket a series of its own beside
// a recipe that is itself named 기타: ECharts keys a legend entry by series name.
export const OTHER_RECIPES = '기타\u200B'
export const TOP_RECIPES = 5

// Daily counts, stacked by the window's most-measured recipes; everything else
// — a measurement with no recipe name included — is 기타. Equal counts rank by
// name, so the stack order does not depend on the order rows arrived in.
export const dailyByRecipe = (rows: UsageRow[], days: string[]): DaySeries[] => {
  const totals = new Map<string, number>()
  for (const r of rows) if (r.recipe) totals.set(r.recipe, (totals.get(r.recipe) ?? 0) + 1)
  const top = [...totals.entries()]
    .sort(([a, x], [b, y]) => y - x || (a < b ? -1 : 1))
    .slice(0, TOP_RECIPES)
    .map(([recipe]) => recipe)
  const index = new Map(days.map((day, i) => [day, i]))
  const series = [...top, OTHER_RECIPES].map(name => ({ name, values: days.map(() => 0) }))
  for (const r of rows) {
    const at = index.get(r.day ?? '')
    if (at === undefined) continue
    const slot = top.indexOf(r.recipe)
    series[slot < 0 ? top.length : slot]!.values[at]! += 1
  }
  return series.filter(s => s.name !== OTHER_RECIPES || s.values.some(Boolean))
}

export interface HourGrid {
  // [day index, hour, count], only where count > 0.
  cells: [number, number, number][]
  max: number
  // Measurements with no usable `time`, left out of every cell.
  missing: number
}

export const hourGrid = (rows: UsageRow[], days: string[]): HourGrid => {
  const index = new Map(days.map((day, i) => [day, i]))
  const counts = new Map<number, number>()
  let missing = 0
  for (const r of rows) {
    const at = index.get(r.day ?? '')
    if (at === undefined) continue
    if (r.hour === null) missing += 1
    else counts.set(at * 24 + r.hour, (counts.get(at * 24 + r.hour) ?? 0) + 1)
  }
  const cells = [...counts.entries()].map(([key, count]): [number, number, number] => [Math.floor(key / 24), key % 24, count])
  return { cells, max: Math.max(0, ...counts.values()), missing }
}

export interface FailureDaily {
  // null: no measurement in the window carries either column, so there is
  // nothing to draw — not "no failures".
  series: { notCompleted: number[], invalid: number[] } | null
  // Measurements a series could not judge because its column is null there.
  notCompletedMissing: number
  invalidMissing: number
}

export const failureDaily = (rows: UsageRow[], days: string[]): FailureDaily => {
  const index = new Map(days.map((day, i) => [day, i]))
  const notCompleted = days.map(() => 0)
  const invalid = days.map(() => 0)
  let notCompletedMissing = 0
  let invalidMissing = 0
  for (const r of rows) {
    const at = index.get(r.day ?? '')
    if (at === undefined) continue
    if (r.notCompleted === null) notCompletedMissing += 1
    else if (r.notCompleted > 0) notCompleted[at]! += 1
    if (r.invalid === null) invalidMissing += 1
    else if (r.invalid > 0) invalid[at]! += 1
  }
  const known = rows.some(r => index.has(r.day ?? '') && (r.notCompleted !== null || r.invalid !== null))
  return { series: known ? { notCompleted, invalid } : null, notCompletedMissing, invalidMissing }
}

// Where a day's column sits in a chart whose plot is inset by `grid` px, as
// CSS for an absolutely positioned box over the chart: a category axis gives
// every day an equal share of the plot's width. null when the day is not drawn.
export const dayBand = (
  days: string[],
  day: string | null,
  grid: { left: number, right: number, top: number, bottom: number }
): Record<string, string> | null => {
  const at = day === null ? -1 : days.indexOf(day)
  if (at < 0) return null
  const plot = `(100% - ${grid.left + grid.right}px)`
  return {
    left: `calc(${grid.left}px + ${plot} * ${at} / ${days.length})`,
    width: `calc(${plot} / ${days.length})`,
    top: `${grid.top}px`,
    bottom: `${grid.bottom}px`
  }
}

// The latest day with a measurement; null with none.
export const latestDay = (rows: UsageRow[]): string | null =>
  rows.reduce<string | null>((latest, r) => r.day !== null && (latest === null || r.day > latest) ? r.day : latest, null)

// One day's measurements, newest first; those with no time last. The filename
// settles a shared time (a MAP608 session), so the order is stable.
export const dayRows = (rows: UsageRow[], day: string): UsageRow[] =>
  rows.filter(r => r.day === day).sort((a, b) =>
    (a.clock === b.clock ? 0 : !a.clock ? 1 : !b.clock ? -1 : a.clock < b.clock ? 1 : -1)
    || (a.row.filename < b.row.filename ? -1 : 1))
