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

export const PARA_KEYS = ['para_16', 'para_13', 'para_9', 'para_5'] as const

export type ParaKey = typeof PARA_KEYS[number]

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
}

/** Structural minimum of `RecipeTrendResponse`. */
export interface ParaTrendInput {
  dates: string[]
  trend: Record<string, Record<string, ParaCounts[]> | undefined>
}

export interface ParaTrendSeries {
  key: ParaKey
  /** Short form used for the direct end-label on each line: `p16`, `p13`, … */
  label: string
  /** One entry per date; `null` marks a date this lot has no row for. */
  values: Array<number | null>
}

export interface ParaTrendData {
  dates: string[]
  /** Always four series in `PARA_KEYS` order, even when empty. */
  series: ParaTrendSeries[]
  /** para_16+13+9+5 per date — the top edge of the stacked area. */
  totals: Array<number | null>
  hasData: boolean
}

export const paraLabel = (key: ParaKey): string => key.replace('para_', 'p')

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
    values: rows.map(row => (row ? row[key] : null))
  }))

  const totals = rows.map(row =>
    row ? PARA_KEYS.reduce((sum, key) => sum + row[key], 0) : null
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
