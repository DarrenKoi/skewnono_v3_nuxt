// Pure helpers for AFM 시계열 비교: what each grouped measurement says about one
// block × column, and the group statistics built on top of that. No DOM/Nuxt
// imports so they run under `node --test`. The formulas are the ones the Claude
// Design proposal 3a (`AFM Trend.dc.html`) defines; the data is the detail
// payload the page already fetches, one request per measurement.
import type { AfmDetailPayload, AfmDetailRow, AfmSummaryItem } from '~/composables/useAfmDetailApi'
import { parseInfoTime } from './afmDuration.ts'
import { tipWidthOf } from './afmInfo.ts'
import { blockNames, blockRows, comparePoints, pointState } from './afmPoints.ts'
import { summaryNumber } from './afmSummary.ts'
import { boxStats, type BoxStats } from './boxplotStats.ts'
import { formatDateTimeLocal } from './dateTime.ts'
import { MAD_TO_SIGMA, mean, medianAbsoluteDeviation, sampleStd } from './stats.ts'

export interface TrendSource {
  filename: string
  recipeName: string
  lotId: string
  slotNumber: number | string
  formattedDate: string
}

export interface TrendEntry {
  // The filename: what the page's one selection (`sel`) holds.
  key: string
  time: number
  lot: string
  slot: string
  recipe: string
  // Re-measurements of one wafer share it. Info's `Sample ID`, else lot.slot.
  sample: string
  payload: AfmDetailPayload
  // Block names by ordinal, and each block's data rows under that name.
  blocks: string[]
  rowsByBlock: Map<string, AfmDetailRow[]>
}

const text = (raw: unknown): string => typeof raw === 'string' ? raw.trim() : ''

// Info's Start Time is the measurement start; the list's date is the fallback.
// The tool's own text (`2026.10.01 00:13:58`) is not a format Date.parse must
// accept, so it is read explicitly first.
const startTime = (source: TrendSource, payload: AfmDetailPayload): number => {
  const raw = text(payload.information['Start Time'])
  const parsed = parseInfoTime(raw) ?? Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : Date.parse(source.formattedDate)
}

// Every data row names its own block (`Site`), with the name its Summary rows
// carry — so a file whose Summary is empty, or that stopped part-way, still
// lines up with its siblings by name. Rows that name none are one block.
export const prepareEntries = (items: { source: TrendSource, payload: AfmDetailPayload }[]): TrendEntry[] => {
  return items.map(({ source, payload }) => {
    const names = blockNames(payload.summary)
    const rowsByBlock = blockRows(payload.data, payload.summary)
    const lot = text(payload.information['Lot ID']) || source.lotId
    const slot = String(source.slotNumber)
    return {
      key: source.filename,
      time: startTime(source, payload),
      lot,
      slot,
      recipe: source.recipeName,
      sample: text(payload.information['Sample ID']) || `${lot}.${slot}`,
      payload,
      blocks: [...new Set([...names, ...rowsByBlock.keys()])],
      rowsByBlock
    }
  }).sort((a, b) => a.time - b.time)
}

// MAD-based σ: one excursion must not widen the limits that are meant to catch
// it. A MAD of 0 (half the values identical) falls back to the sample STDEV.
export const robustSd = (values: number[]): number =>
  MAD_TO_SIGMA * medianAbsoluteDeviation(values) || sampleStd(values)

export interface ControlLimits {
  mu: number
  sigma: number
  ucl: number
  lcl: number
}

// μ ± 3σ over the group. One value has no spread, so it gets no limits.
export const controlLimits = (values: number[]): ControlLimits | null => {
  if (values.length < 2) return null
  const mu = mean(values)
  const sigma = robustSd(values)
  return { mu, sigma, ucl: mu + 3 * sigma, lcl: mu - 3 * sigma }
}

export const isOutside = (value: number, limits: ControlLimits | null): boolean =>
  limits !== null && (value > limits.ucl || value < limits.lcl)

// Five-number summary of one measurement's point values (R-7 quartiles).
export const quartiles = (values: number[]): BoxStats | null => boxStats(values)

export type TrendStat = AfmSummaryItem

export interface MeasurementStats extends Record<TrendStat, number | null> {
  // Where the five statistics came from. Data-derived ones keep every row,
  // FAILED and Valid=FALSE included — the tool's own Summary does the same.
  source: 'summary' | 'data'
  // The block's data rows, and those COMPLETED with Valid not stated FALSE.
  // Null when the file has no data table.
  n: number | null
  nValid: number | null
  // Point → value, and their quartiles. Empty / null without a data table.
  points: Map<string, number>
  box: BoxStats | null
}

const ITEMS: TrendStat[] = ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']

// The one rule for a row that counts as a good reading: COMPLETED, with Valid
// not stated FALSE. `nValid` counts by it and 측정 항목 간 관계 pairs by it.
export const isValidRow = (row: AfmDetailRow): boolean => row.State === 'COMPLETED' && row.Valid !== false

// Point → value for one block × column. A repeat recipe's later lap replaces
// the earlier one. `validOnly` drops rows failing `isValidRow` BEFORE that
// rule: a point whose last lap FAILED shows its last valid lap, and a point
// with no valid row is absent.
export const pointValues = (entry: TrendEntry, block: string, column: string, validOnly = false): Map<string, number> => {
  const points = new Map<string, number>()
  for (const row of entry.rowsByBlock.get(block) ?? []) {
    const value = summaryNumber(row[column])
    if (value !== null && (!validOnly || isValidRow(row))) points.set(row.measurement_point, value)
  }
  return points
}

// One measurement's statistics for a block × column: the Summary's when it has
// them, else computed from the data rows. Null when neither carries a value.
export const measurementStats = (entry: TrendEntry, block: string, column: string): MeasurementStats | null => {
  const rows = entry.rowsByBlock.get(block) ?? []
  const points = pointValues(entry, block, column)
  const values = [...points.values()]
  const counts = {
    n: entry.payload.data.length ? rows.length : null,
    nValid: entry.payload.data.length
      ? rows.filter(isValidRow).length
      : null,
    points,
    box: quartiles(values)
  }

  const summaryRows = entry.payload.summary.filter(row => row.Site === block)
  const fromSummary = Object.fromEntries(ITEMS.map(item =>
    [item, summaryNumber(summaryRows.find(row => row.ITEM === item)?.[column])]
  )) as Record<TrendStat, number | null>
  if (ITEMS.some(item => fromSummary[item] !== null)) return { ...fromSummary, source: 'summary', ...counts }

  if (!values.length) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  return { MEAN: mean(values), STDEV: sampleStd(values), MIN: min, MAX: max, RANGE: max - min, source: 'data', ...counts }
}

// Why a measurement has no statistics for a block.
export const missingReason = (entry: TrendEntry, block: string): string => {
  const rows = entry.rowsByBlock.get(block) ?? []
  return rows.length && rows.every(row => row.State === 'STOPPED') ? '블록 STOPPED' : '블록 없음'
}

export interface RecipeCentre {
  // Mean of the recipe's values, and its μ ± 3σ (null under two values) — of
  // its pinned baseline alone when the group has one.
  mu: number | null
  // How many values μ and the limits were taken from.
  n: number
  limits: ControlLimits | null
  // Why a pinned baseline gives this recipe no band; empty otherwise.
  reason: string
}

export interface TrendRow {
  entry: TrendEntry
  stats: MeasurementStats | null
  // 'baseline' when the measurement is pinned as part of the fixed reference.
  role: 'baseline' | 'target'
  // The picked statistic, its distance from the recipe's μ, and whether it
  // sits outside the recipe's limits (never, while the limits are off, and
  // never for a baseline measurement: it is not judged against itself).
  value: number | null
  delta: number | null
  out: boolean
  // Worst point state over every block; null without a data table.
  state: string | null
  // Why `stats` is null; empty when it is not.
  reason: string
}

// What the μ ± 3σ band is called. It is computed from measurements the user
// chose — the group, or the pinned baseline — so it is a reference range, never
// a control or spec limit (the data cannot support that claim).
export const trendBandName = (pinned: boolean): string => pinned ? '고정 기준 범위' : '그룹 기준 범위'

// One row per measurement for the picked block × column × statistic. μ and the
// limits are per recipe: a group that mixes recipes gets one series each, and
// a column of the same name may not be the same quantity across them.
// `baselineKeys` (고정 기준선) pins the measurements μ and the limits are taken
// from, so the reference stays put as the group grows; keys that name nothing
// in the group pin nothing.
export const trendRows = (
  entries: TrendEntry[],
  block: string,
  column: string,
  stat: TrendStat,
  showLimits: boolean,
  baselineKeys?: ReadonlySet<string>
): { rows: TrendRow[], centres: Map<string, RecipeCentre> } => {
  const pinned = entries.some(entry => baselineKeys?.has(entry.key))
  const base = entries.map((entry) => {
    const stats = measurementStats(entry, block, column)
    const role: TrendRow['role'] = baselineKeys?.has(entry.key) ? 'baseline' : 'target'
    return { entry, stats, role, value: stats?.[stat] ?? null }
  })
  const centres = new Map<string, RecipeCentre>()
  for (const recipe of new Set(entries.map(entry => entry.recipe))) {
    const values = base.flatMap(row =>
      row.entry.recipe === recipe && (!pinned || row.role === 'baseline') ? row.value ?? [] : [])
    const limits = controlLimits(values)
    centres.set(recipe, { mu: values.length ? mean(values) : null, n: values.length, limits, reason: pinned && !limits ? '기준 표본 부족' : '' })
  }
  const rows = base.map((row) => {
    const centre = centres.get(row.entry.recipe)!
    return {
      ...row,
      delta: row.value !== null && centre.mu !== null ? row.value - centre.mu : null,
      out: showLimits && row.role === 'target' && row.value !== null && isOutside(row.value, centre.limits),
      state: pointState(row.entry.payload.data),
      reason: row.stats ? '' : missingReason(row.entry, block)
    }
  })
  return { rows, centres }
}

// 측정별 요약 as a sheet: the on-screen columns, with Lot · Slot and n (유효)
// split so each cell holds one number Excel can sort. The time keeps its year,
// which the screen's `shortTime` drops: a sheet outlives the screen. A time that
// never parsed stays blank — `toISOString` on NaN would throw out of the export.
export const entryTimeText = (entry: Pick<TrendEntry, 'time'>): string =>
  Number.isFinite(entry.time) ? formatDateTimeLocal(new Date(entry.time).toISOString()) : ''

export const trendTable = (rows: TrendRow[]): { headers: string[], rows: unknown[][] } => ({
  headers: ['시각', 'Recipe', 'Lot', 'Slot', 'n', 'n (유효)', 'MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE', 'Δ μ', '상태', '파일'],
  rows: rows.map(({ entry, stats, delta, state, reason }) => [
    entryTimeText(entry),
    entry.recipe, entry.lot, entry.slot,
    stats?.n ?? null, stats?.nValid ?? null,
    stats?.MEAN ?? null, stats?.STDEV ?? null, stats?.MIN ?? null, stats?.MAX ?? null, stats?.RANGE ?? null,
    delta, stats ? state : reason, entry.key
  ])
})

// 포인트별 비교's rows. `validOnly` swaps each measurement's point values for
// those of its valid rows; the statistics 01 reads stay as they are. `invalid`
// counts the rows the choice is about: a number in the column, not `isValidRow`.
export const pointScope = (rows: TrendRow[], block: string, column: string, validOnly: boolean): { rows: TrendRow[], invalid: number } => ({
  rows: validOnly
    ? rows.map(row => row.stats ? { ...row, stats: { ...row.stats, points: pointValues(row.entry, block, column, true) } } : row)
    : rows,
  invalid: rows.reduce((sum, { entry }) => sum + (entry.rowsByBlock.get(block) ?? [])
    .filter(row => !isValidRow(row) && summaryNumber(row[column]) !== null).length, 0)
})

export type PointBaseline = 'mean' | 'first' | 'selected'

export interface PointMatrix {
  points: string[]
  rows: { key: string, values: (number | null)[] }[]
  baseline: (number | null)[]
  // 'selected' falls back to the group mean when the selection has no values.
  baselineUsed: PointBaseline
}

// Point × measurement values, plus the reference line the Δ view subtracts.
// `series` is in time order, so 'first' is its head.
export const pointMatrix = (
  series: { key: string, points: Map<string, number> }[],
  baseline: PointBaseline,
  selectedKey: string | null
): PointMatrix => {
  const points = [...new Set(series.flatMap(s => [...s.points.keys()]))].sort(comparePoints)
  const rows = series.map(s => ({ key: s.key, values: points.map(p => s.points.get(p) ?? null) }))
  const groupMean = points.map((_, i) => {
    const column = rows.flatMap(row => row.values[i] ?? [])
    return column.length ? mean(column) : null
  })
  const reference = baseline === 'first' ? rows[0] : baseline === 'selected' ? rows.find(row => row.key === selectedKey) : undefined
  return {
    points,
    rows,
    baseline: reference ? reference.values : groupMean,
    baselineUsed: reference || baseline === 'mean' ? baseline : 'mean'
  }
}

export interface PointStability {
  point: string
  // Inter-measurement STDEV; null with fewer than two values at the point.
  sd: number | null
  unstable: boolean
}

// A point is unstable when its STDEV across measurements clears mean + 1.5·sd
// of every point's STDEV.
export const pointStability = (matrix: PointMatrix): PointStability[] => {
  const sds = matrix.points.map((_, i) => {
    const column = matrix.rows.flatMap(row => row.values[i] ?? [])
    return column.length >= 2 ? sampleStd(column) : null
  })
  const known = sds.filter((sd): sd is number => sd !== null)
  const cut = mean(known) + 1.5 * sampleStd(known)
  return matrix.points.map((point, i) => ({ point, sd: sds[i]!, unstable: sds[i] != null && sds[i]! > cut }))
}

export interface VarianceSplit {
  // STDEV of the measurements' MEANs, and the mean of their STDEVs.
  lotSd: number
  waferSd: number
  // lot share of lot² + wafer², 0–100.
  lotPct: number
}

export const varianceSplit = (stats: Pick<MeasurementStats, 'MEAN' | 'STDEV'>[]): VarianceSplit | null => {
  const means = stats.flatMap(s => s.MEAN ?? [])
  const sds = stats.flatMap(s => s.STDEV ?? [])
  if (means.length < 2 || !sds.length) return null
  const lotSd = sampleStd(means)
  const waferSd = mean(sds)
  const total = lotSd ** 2 + waferSd ** 2
  return { lotSd, waferSd, lotPct: total ? Math.round(100 * lotSd ** 2 / total) : 0 }
}

export interface RepeatPair {
  sample: string
  recipe: string
  keys: string[]
  hours: number
  // MAX − MIN of the re-measurements' MEANs, and that over the wafer σ̄.
  spread: number
  ratio: number | null
}

// Re-measurements of one sample by one recipe (a different recipe measures a
// different thing, so it is not a repeat), kept only where two of them have a
// MEAN to compare. Entries arrive in time order; the wafer σ̄ is the recipe's.
export const repeatPairs = (
  entries: { key: string, sample: string, recipe: string, time: number, mean: number | null }[],
  waferSdOf: (recipe: string) => number | null
): RepeatPair[] => {
  const groups = new Map<string, typeof entries>()
  for (const entry of entries) {
    const id = `${entry.recipe}\u0000${entry.sample}`
    const group = groups.get(id)
    if (group) group.push(entry)
    else groups.set(id, [entry])
  }
  return [...groups.values()].flatMap((group) => {
    const means = group.flatMap(entry => entry.mean ?? [])
    if (means.length < 2) return []
    const spread = Math.max(...means) - Math.min(...means)
    const waferSd = waferSdOf(group[0]!.recipe)
    return [{
      sample: group[0]!.sample,
      recipe: group[0]!.recipe,
      keys: group.map(entry => entry.key),
      hours: (group[group.length - 1]!.time - group[0]!.time) / 3_600_000,
      spread,
      ratio: waferSd ? spread / waferSd : null
    }]
  })
}

export interface HealthPoint {
  key: string
  time: number
  // Points not COMPLETED.
  notCompleted: number
  approach: number | null
  mileage: number | null
  // From the measurement's Info, not its rows. `tip` is both the tip's identity
  // and its label: one Tip ID sits in several cassette slots, so the ID alone
  // does not say which tip (office 확인 2026-10-06). `tipWidth` is what that
  // measurement recorded, not a spec of the tip; null where it recorded none.
  tip: string | null
  tipWidth: number | null
  // Info's `Last Pick Up Time`: a value of the tip, the same on every
  // measurement it makes, so a new one is a re-pick. Absent where the source
  // does not carry it.
  pickUp?: string | null
}

const meanOf = (rows: AfmDetailRow[], column: string): number | null => {
  const values = rows.flatMap(row => summaryNumber(row[column]) ?? [])
  return values.length ? mean(values) : null
}

// What identifies one physical tip, in label order: the ID, then where it sits.
const TIP_KEYS = ['Tip ID', 'Tip Cassette ID', 'Tip Port No', 'Tip Slot No']

// Every data row of every block — health does not depend on the block pick.
export const healthSeries = (entries: TrendEntry[]): HealthPoint[] =>
  entries.map(({ key, time, payload: { data, information } }) => {
    const [id, ...seat] = TIP_KEYS.map(k => String(information[k] ?? '').trim())
    return {
      key,
      time,
      notCompleted: data.filter(row => row.State !== 'COMPLETED').length,
      approach: meanOf(data, 'Approach Count'),
      mileage: meanOf(data, 'Mileage'),
      tip: id ? `${id} · ${seat.map(v => v || '?').join('/')}` : null,
      tipWidth: tipWidthOf(information),
      pickUp: String(information['Last Pick Up Time'] ?? '').trim() || null
    }
  })

// The times at which the tip is a different one from the last measurement that
// named its tip: its ID or seat differs, or — a new tip in the same seat — its
// Mileage fell AND it was picked up anew. The counter belongs to the tip and
// was never seen to fall on one, but a restart or a manual reset is unobserved,
// so a fall alone is not taken as a change (office 확인 2026-10-07; nothing
// records the change itself). A measurement with no Tip ID neither is nor
// hides a change.
export const tipChanges = (health: HealthPoint[]): number[] => {
  const named = [...health].filter(h => h.tip !== null).sort((a, b) => a.time - b.time)
  return named.flatMap((h, i) => {
    const last = named[i - 1]
    if (!last) return []
    const fell = h.mileage !== null && last.mileage !== null && h.mileage < last.mileage
    const repicked = !!h.pickUp && !!last.pickUp && h.pickUp !== last.pickUp
    return h.tip !== last.tip || (fell && repicked) ? [h.time] : []
  })
}

// `MM/DD HH:mm`, local — the trend's tick and row format.
export const shortTime = (time: number): string => {
  const d = new Date(time)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export const fmt2 = (value: number | null | undefined): string =>
  value == null || !Number.isFinite(value) ? '–' : value.toFixed(2)
