// Pure helpers for 시계열 비교's 측정 항목 간 관계: two columns of one point row
// as an (x, y) sample, over the measurements of a group. No DOM/Nuxt imports so
// they run under `node --test`.
import { isMeasurementKey } from './afmExport.ts'
import { summaryNumber } from './afmSummary.ts'
import { isValidRow, type TrendEntry } from './afmTrend.ts'
import { pearson } from './stats.ts'

// Per-row tip usage, offered on X only. Shown under the raw column name:
// Mileage's unit is not confirmed.
const USAGE_COLUMNS = ['Mileage', 'Approach Count']

// What the pickers offer for a block: the columns that hold a number in some
// row of it. Measured columns are the recipe's own, in natural order.
export const relationColumns = (entries: TrendEntry[], block: string): { measured: string[], usage: string[] } => {
  const numeric = new Set<string>()
  for (const entry of entries) {
    for (const row of entry.rowsByBlock.get(block) ?? []) {
      for (const key of Object.keys(row)) if (summaryNumber(row[key]) !== null) numeric.add(key)
    }
  }
  return {
    measured: [...numeric].filter(isMeasurementKey).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })),
    usage: USAGE_COLUMNS.filter(key => numeric.has(key))
  }
}

export interface RelationSample {
  // The measurement (filename) and the point the row belongs to.
  key: string
  point: string
  x: number
  y: number
}

export interface Relation {
  samples: RelationSample[]
  // Rows of the block left out by `isValidRow` (not COMPLETED, or Valid FALSE).
  excluded: number
  // Rows that pass it but have no number in one of the two columns.
  unpaired: number
  // Samples whose Valid is not stated — kept, but not confirmed valid.
  unknownValid: number
}

// One sample per data row of the block that has a number in both columns. A
// row is never paired with another row: a repeat recipe's laps are each their
// own sample, and nothing is averaged first.
export const relationSamples = (entries: TrendEntry[], block: string, xColumn: string, yColumn: string): Relation => {
  const relation: Relation = { samples: [], excluded: 0, unpaired: 0, unknownValid: 0 }
  for (const entry of entries) {
    for (const row of entry.rowsByBlock.get(block) ?? []) {
      const x = summaryNumber(row[xColumn])
      const y = summaryNumber(row[yColumn])
      if (!isValidRow(row)) relation.excluded++
      else if (x === null || y === null) relation.unpaired++
      else {
        relation.samples.push({ key: entry.key, point: row.measurement_point, x, y })
        if (row.Valid !== true) relation.unknownValid++
      }
    }
  }
  return relation
}

// Under this many samples the section shows no statistic (the floor `pearson`
// itself has: two points are always collinear).
export const RELATION_MIN_SAMPLES = 3

export interface RelationSummary {
  n: number
  // Pearson r; null under the floor or when one axis does not vary.
  r: number | null
}

// No y − x statistic on purpose: two columns in the same unit are not known to
// be the same quantity, so a difference is not offered as a metric
// (docs/afm/service-recommendations.md 7.3).
export const relationSummary = (samples: RelationSample[]): RelationSummary => {
  const n = samples.length
  return { n, r: n < RELATION_MIN_SAMPLES ? null : pearson(samples.map(s => [s.x, s.y])) }
}
