// Shapes a focused lot's parameter counts across the weekly trend dates.
//
// This module exists to keep ABSOLUTE COUNTS absolute. The chart it feeds used
// to normalise twice over — the stacked area divided each date by that date's
// own total (so four paras doubling moved nothing), and the per-para lines each
// divided by their own max (so no two lines were comparable and no real number
// was ever shown). Both were layout workarounds for a 60px sparkline that no
// caller renders any more. Nothing here divides; the counts that come out are
// the counts that came off the wire.
//
// Deliberately free of framework imports so it runs under `node --test` with
// Node's type stripping, like the rest of app/utils.

// Highest measurement density first — the stacked area and the colour ramp both
// read top-down in this order.
//
// These are RANGES of point count, not exact values (backend
// `para_buckets.py` owns the boundaries; this is the mirrored copy that exists
// only because the two sides are different languages):
//
//   para_over_16  16 < x        para_16  13 < x <= 16    para_13  9 < x <= 13
//   para_9        5 < x <= 9    para_5   x <= 5
//
// Every parameter lands in exactly one, so the five sum to `para_all` and the
// five percentages always total 100.
export const PARA_KEYS = ['para_over_16', 'para_16', 'para_13', 'para_9', 'para_5'] as const

export type ParaKey = typeof PARA_KEYS[number]

/** Range label for a bucket key — `p16` would now be a lie about the boundary. */
const PARA_LABELS: Record<ParaKey, string> = {
  para_over_16: '>16',
  para_16: '14–16',
  para_13: '10–13',
  para_9: '6–9',
  para_5: '≤5'
}

/**
 * The structural minimum of `SummaryRow` this module reads. Declared locally
 * rather than imported from the API composable so the module stays alias-free;
 * `SummaryRow` satisfies it structurally, so callers pass their rows unchanged.
 */
export interface ParaCounts {
  lot_cd: string
  para_16: number
  para_13: number
  para_9: number
  para_5: number
  /**
   * Optional on purpose. Weekly snapshots written before 2026-08-10 have no
   * such key, and the trend view reads up to eight weeks back — treating a
   * missing bucket as `undefined` would poison every total with `NaN`.
   */
  para_over_16?: number
}

/** Structural minimum of `RecipeTrendResponse`. */
export interface ParaTrendInput {
  dates: string[]
  trend: Record<string, Record<string, ParaCounts[]> | undefined>
}

export interface ParaTrendSeries {
  key: ParaKey
  /** Range label used for the direct end-label on each line: `14–16`, `>16`, … */
  label: string
  /** One entry per date; `null` marks a date this lot has no row for. */
  values: Array<number | null>
}

export interface ParaTrendData {
  dates: string[]
  /** Always one series per `PARA_KEYS` entry, in that order, even when empty. */
  series: ParaTrendSeries[]
  /** Sum of every bucket per date — the top edge of the stacked area. */
  totals: Array<number | null>
  hasData: boolean
}

export const paraLabel = (key: ParaKey): string => PARA_LABELS[key]

/** A bucket's count, reading a pre-2026-08-10 snapshot's missing key as 0. */
const paraValue = (row: ParaCounts, key: ParaKey): number => row[key] ?? 0

const emptySeries = (): ParaTrendSeries[] =>
  PARA_KEYS.map(key => ({ key, label: paraLabel(key), values: [] }))

/**
 * Pull one lot's counts out of the trend payload, one value per date.
 *
 * A date the lot has no row for yields `null`, not `0`. The distinction is real:
 * zero asserts the lot was measured and had no parameters that week, while null
 * says it was not sampled at all. ECharts renders null as a gap in the line and
 * a hole in the stack, which is the honest reading.
 */
export const extractParaTrend = (
  trend: ParaTrendInput | null | undefined,
  bucket: string,
  lotCd: string | null
): ParaTrendData => {
  const dates = trend?.dates ?? []

  if (!trend || !lotCd || dates.length === 0) {
    return { dates: [], series: emptySeries(), totals: [], hasData: false }
  }

  const rows = dates.map(date =>
    trend.trend[date]?.[bucket]?.find(row => row.lot_cd === lotCd) ?? null
  )

  const series = PARA_KEYS.map(key => ({
    key,
    label: paraLabel(key),
    values: rows.map(row => (row ? paraValue(row, key) : null))
  }))

  const totals = rows.map(row =>
    row ? PARA_KEYS.reduce((sum, key) => sum + paraValue(row, key), 0) : null
  )

  return { dates, series, totals, hasData: rows.some(row => row !== null) }
}

/**
 * `MM/DD` axis tick from an ISO date. Left as-is if it is not `YYYY-MM-DD`,
 * so an unexpected format degrades to something readable instead of `NaN/NaN`.
 */
export const formatTrendTick = (date: string): string => {
  const parts = date.split('-')
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : date
}
