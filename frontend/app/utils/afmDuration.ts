// How long each grouped AFM measurement ran, from Info's Start Time / End Time.
// No DOM/Nuxt imports so they run under `node --test`.
import type { TrendEntry } from './afmTrend.ts'
import { median } from './stats.ts'

export type DurationReason = 'no-times' | 'no-end' | 'no-start' | 'bad-format' | 'reversed'
export type Duration
  = | { kind: 'ok', seconds: number }
    | { kind: 'none', reason: DurationReason }

export const DURATION_REASON_LABEL: Record<DurationReason, string> = {
  'no-times': 'Start·End Time 없음',
  'no-end': 'End Time 없음',
  'no-start': 'Start Time 없음',
  'bad-format': '시각 형식 미지원',
  'reversed': '종료가 시작보다 이름'
}

const KST_OFFSET_MS = 9 * 3600_000
const TIME_PATTERN = /^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})$/

// `YYYY.MM.DD HH:mm:ss` read as KST, independent of the machine's timezone.
export const parseInfoTime = (raw: unknown): number | null => {
  const match = typeof raw === 'string' ? TIME_PATTERN.exec(raw.trim()) : null
  if (!match) return null
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number) as [number, number, number, number, number, number]
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second))
  // Date.UTC rolls 02.30 over to 03.02; a round-trip catches that.
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day || hour > 23 || minute > 59 || second > 59) return null
  return date.getTime() - KST_OFFSET_MS
}

// Info values are not all text (AfmInformation allows numbers); a non-string is present but unparseable.
const present = (raw: unknown): unknown => typeof raw === 'string' ? (raw.trim() ? raw : null) : raw ?? null

export const durationOf = (information: Record<string, unknown>): Duration => {
  const start = present(information['Start Time'])
  const end = present(information['End Time'])
  if (start === null && end === null) return { kind: 'none', reason: 'no-times' }
  if (end === null) return { kind: 'none', reason: 'no-end' }
  if (start === null) return { kind: 'none', reason: 'no-start' }
  const from = parseInfoTime(start)
  const to = parseInfoTime(end)
  if (from === null || to === null) return { kind: 'none', reason: 'bad-format' }
  if (to < from) return { kind: 'none', reason: 'reversed' }
  return { kind: 'ok', seconds: (to - from) / 1000 }
}

export interface DurationRow {
  entry: TrendEntry
  duration: Duration
  // seconds ÷ the recipe's median; null until the recipe has 3 durations.
  ratio: number | null
}

const MIN_FOR_RATIO = 3

const okSeconds = (rows: DurationRow[]): number[] =>
  rows.flatMap(row => row.duration.kind === 'ok' ? [row.duration.seconds] : [])

export const durationRows = (entries: TrendEntry[]): DurationRow[] => {
  const durations = entries.map(entry => durationOf(entry.payload.information))
  const byRecipe = new Map<string, number[]>()
  entries.forEach((entry, i) => {
    const d = durations[i]!
    if (d.kind === 'ok') byRecipe.set(entry.recipe, [...(byRecipe.get(entry.recipe) ?? []), d.seconds])
  })
  const medians = new Map<string, number>()
  for (const [recipe, seconds] of byRecipe) {
    if (seconds.length >= MIN_FOR_RATIO) medians.set(recipe, median(seconds))
  }
  return entries.map((entry, i) => {
    const duration = durations[i]!
    const mid = medians.get(entry.recipe)
    return {
      entry,
      duration,
      ratio: duration.kind === 'ok' && mid !== undefined && mid > 0 ? duration.seconds / mid : null
    }
  })
}

export interface RecipeDuration {
  recipe: string
  total: number
  counted: number
  median: number | null
  min: number | null
  max: number | null
}

export const durationByRecipe = (rows: DurationRow[]): RecipeDuration[] => {
  const groups = new Map<string, DurationRow[]>()
  for (const row of rows) {
    const list = groups.get(row.entry.recipe)
    if (list) list.push(row)
    else groups.set(row.entry.recipe, [row])
  }
  return [...groups].map(([recipe, list]) => {
    const seconds = okSeconds(list)
    const any = seconds.length > 0
    return {
      recipe,
      total: list.length,
      counted: seconds.length,
      median: any ? median(seconds) : null,
      min: any ? Math.min(...seconds) : null,
      max: any ? Math.max(...seconds) : null
    }
  })
}

// 5925 → '1시간 38분 45초'; zero units are dropped, 0 stays '0초'.
export const formatDuration = (seconds: number): string => {
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor(total % 3600 / 60)
  const s = total % 60
  const parts = [h && `${h}시간`, m && `${m}분`, (s || !total) && `${s}초`].filter(Boolean)
  return parts.join(' ')
}
