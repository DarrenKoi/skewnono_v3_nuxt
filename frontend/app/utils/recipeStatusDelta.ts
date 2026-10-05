// Recipe 현황: 이전 동일 기간 대비 원시 변화.
//
// Pure on purpose. The views fetch the same summary endpoint a second time for
// the window returned by `previousWindow`, and everything from there to the
// rendered text is decided here.
//
// Run: node --test app/utils/recipeStatusDelta.test.ts

import type { RecipeTatSummary } from '~/composables/useRecipeTatApi'
import type { FailIssueSummary } from '~/composables/useFailIssueApi'
import { shiftIsoDate } from './dateTime.ts'

export type RecipeStatusDeltaTone = 'ok' | 'bad' | 'neutral' | 'none'

export type TatDeltaKey = 'totalTat' | 'distinctRecipes' | 'totalExecutions' | 'avgMeastime'
export type FailDeltaKey = 'failCount' | 'totalMeasurements' | 'failRatio'

export interface RecipeStatusDeltaItem<K extends string = string> {
  key: K
  delta: string
  tone: RecipeStatusDeltaTone
  title: string
}

export const NO_PREVIOUS_PERIOD = '이전 기간 없음'

const DAY_MS = 86_400_000

const utcDay = (iso: string): number => {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)
}

const inclusiveDays = (start: string, end: string): number =>
  Math.round((utcDay(end) - utcDay(start)) / DAY_MS) + 1

/**
 * The window of the same length immediately before `[start, end]`.
 *
 * Both bounds are inclusive calendar days, so a 7-day window ending 09-28
 * (09-22..09-28) is preceded by 09-15..09-21. UTC arithmetic via
 * `shiftIsoDate`: the inputs carry no time-of-day to preserve.
 */
export const previousWindow = (
  start: string,
  end: string
): { start: string, end: string } => {
  const len = Math.max(1, inclusiveDays(start, end))
  return { start: shiftIsoDate(start, len), end: shiftIsoDate(start, 1) }
}

/**
 * Whether the displayed window still contains the anchor day, which is the
 * one day that is not finished yet. `>=` rather than `===`: a hand-typed end
 * past the anchor includes it just the same.
 */
export const isAnchorIncluded = (end: string, anchorDate: string): boolean =>
  Boolean(end) && Boolean(anchorDate) && end >= anchorDate.slice(0, 10)

// U+2212, not a hyphen: it is as wide as `+` in the mono face, so signed
// columns line up.
const MINUS = '−'
const sign = (n: number): string => n > 0 ? '+' : n < 0 ? MINUS : ''
const signedCount = (n: number): string => `${sign(n)}${Math.abs(n).toLocaleString('en-US')}`

/** ` (+9.8%)`, or nothing when the previous value gives no base to divide by. */
const percentSuffix = (cur: number, prev: number): string => {
  if (!(prev > 0)) return ''
  const pct = Number(((cur - prev) / prev * 100).toFixed(1))
  return ` (${sign(pct)}${Math.abs(pct).toFixed(1)}%)`
}

const lowerIsOk = (diff: number): RecipeStatusDeltaTone =>
  diff < 0 ? 'ok' : diff > 0 ? 'bad' : 'neutral'

const countDelta = (cur: number, prev: number) => ({
  delta: `${signedCount(cur - prev)}${percentSuffix(cur, prev)}`,
  tone: 'neutral' as const
})

const secondsDelta = (
  cur: number,
  prev: number,
  formatSeconds: (seconds: number) => string
) => {
  // Round first so the sign, the text and the tone all describe one number.
  const diff = Math.round(cur) - Math.round(prev)
  return {
    delta: `${sign(diff)}${formatSeconds(Math.abs(diff))}${percentSuffix(cur, prev)}`,
    tone: lowerIsOk(diff)
  }
}

/** Rates are 0..1 fractions; the difference is reported in percentage points. */
const rateDelta = (cur: number, prev: number) => {
  const points = Number(((cur - prev) * 100).toFixed(1))
  return {
    delta: `${sign(points)}${Math.abs(points).toFixed(1)}%p`,
    tone: lowerIsOk(points)
  }
}

interface WindowedSummary {
  start_date: string | null
  end_date: string | null
  total_executions: number
}

const windowLabel = (prev: WindowedSummary): string => {
  if (!prev.start_date || !prev.end_date) return '이전 기간'
  const days = inclusiveDays(prev.start_date, prev.end_date)
  return `이전 ${days}일(${prev.start_date.slice(5)}~${prev.end_date.slice(5)})`
}

const count = (n: number): string => n.toLocaleString('en-US')

type Computed = { delta: string, tone: RecipeStatusDeltaTone }

const assemble = <K extends string>(
  cur: WindowedSummary,
  prev: WindowedSummary | null | undefined,
  compute: (key: K) => Computed,
  keys: readonly K[]
): RecipeStatusDeltaItem<K>[] => {
  if (!prev || !(prev.total_executions > 0)) {
    const title = prev
      ? `${windowLabel(prev)} 0건 · 현재 ${count(cur.total_executions)}건`
      : ''
    return keys.map(key => ({ key, delta: NO_PREVIOUS_PERIOD, tone: 'none', title }))
  }
  const title = `${windowLabel(prev)} ${count(prev.total_executions)}건 대비`
    + ` · 현재 ${count(cur.total_executions)}건`
  return keys.map(key => ({ key, ...compute(key), title }))
}

const TAT_KEYS = ['totalTat', 'distinctRecipes', 'totalExecutions', 'avgMeastime'] as const
const FAIL_KEYS = ['failCount', 'totalMeasurements', 'failRatio'] as const

/**
 * Per-KPI change for the Recipe TAT strip.
 *
 * `formatSeconds` is passed in rather than imported: the app's formatter
 * (`formatSecondsAsDuration`) lives beside `$fetch` code that `node --test`
 * cannot load.
 */
export const tatDeltaItems = (
  cur: RecipeTatSummary,
  prev: RecipeTatSummary | null | undefined,
  formatSeconds: (seconds: number) => string
): RecipeStatusDeltaItem<TatDeltaKey>[] => assemble(cur, prev, (key) => {
  const p = prev as RecipeTatSummary
  switch (key) {
    case 'totalTat': return secondsDelta(cur.total_tat_seconds, p.total_tat_seconds, formatSeconds)
    case 'distinctRecipes': return countDelta(cur.total_recipes, p.total_recipes)
    case 'totalExecutions': return countDelta(cur.total_executions, p.total_executions)
    case 'avgMeastime': return secondsDelta(cur.avg_meastime, p.avg_meastime, formatSeconds)
  }
}, TAT_KEYS)

/**
 * Per-KPI change for the Align / Meas fail strip.
 *
 * The fail *count* stays `neutral`: it moves with volume, so only the rate
 * carries a direction.
 */
export const failDeltaItems = (
  cur: FailIssueSummary,
  prev: FailIssueSummary | null | undefined,
  section: 'align' | 'meas'
): RecipeStatusDeltaItem<FailDeltaKey>[] => assemble(cur, prev, (key) => {
  const p = prev as FailIssueSummary
  const countKey = section === 'align' ? 'align_fail_count' : 'meas_fail_count'
  const rateKey = section === 'align' ? 'align_fail_rate' : 'meas_fail_rate'
  switch (key) {
    case 'failCount': return countDelta(cur[countKey], p[countKey])
    case 'totalMeasurements': return countDelta(cur.total_executions, p.total_executions)
    case 'failRatio': return rateDelta(cur[rateKey], p[rateKey])
  }
}, FAIL_KEYS)
