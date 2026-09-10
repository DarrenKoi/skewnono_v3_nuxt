// Date and timestamp formatting. Before this module the same four formatters
// had been re-typed across ~19 sites, and they had NOT stayed identical:
// export filenames were built from UTC while chart PNG filenames used local
// time, so in KST (+09) an Excel file and a PNG downloaded from the same page before
// 09:00 carried different dates.
//
// Nothing here is timezone-clever. Everything is local time except
// `shiftIsoDate`, which is deliberately UTC — see its comment.

import { formatDateStamp } from './chartExport.ts'

const pad = (n: number) => String(n).padStart(2, '0')

/**
 * Today as `YYYY-MM-DD` in the viewer's timezone, for export filenames.
 *
 * Local, not UTC. A filename date is something the user reads next to their
 * own clock, so `new Date().toISOString().slice(0, 10)` was wrong for every
 * KST morning before 09:00. Delegates to `formatDateStamp` so Excel and PNG
 * exports can never disagree about what day it is.
 */
export const todayStamp = (): string => formatDateStamp(new Date())

/**
 * Subtract days from a `YYYY-MM-DD` string, staying on calendar days.
 *
 * UTC on purpose: the input has no time-of-day, so constructing it in local
 * time would let a DST transition or a timezone offset push the result onto
 * the neighbouring day. There is no wall clock here to preserve.
 */
export const shiftIsoDate = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export interface FormatDateTimeOptions {
  /** Append `:ss`. */
  withSeconds?: boolean
  /** Returned when the input is empty or unparseable. Defaults to the input. */
  fallback?: string
}

/**
 * `YYYY-MM-DD HH:mm` in local time — the table/detail timestamp format.
 *
 * The fallback is a parameter rather than a fixed value because call sites
 * disagreed on it: most echo the unparseable input back so a malformed
 * timestamp is visible rather than silently blank, but CompareCart renders an
 * empty cell instead. Both are defensible; neither is worth changing blind,
 * since the mocks never emit an unparseable timestamp and no home test can
 * tell the two apart.
 */
export const formatDateTimeLocal = (
  iso: string | null | undefined,
  opts: FormatDateTimeOptions = {}
): string => {
  if (!iso) return opts.fallback ?? ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return opts.fallback ?? iso

  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return opts.withSeconds
    ? `${base} ${time}:${pad(date.getSeconds())}`
    : `${base} ${time}`
}

/**
 * `YYYY-MM-DDTHH:mm` — the value shape `<input type="datetime-local">` wants.
 *
 * Must stay local: the control has no timezone concept and displays whatever
 * string it is given as wall-clock time.
 */
export const formatDateTimeInput = (date: Date): string =>
  `${formatDateStamp(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`

/**
 * Korean locale timestamp (`2026. 8. 8. 14:38:00`) for admin/activity screens.
 *
 * Deliberately NOT the same as `formatDateTimeLocal`: these screens show
 * server-recorded audit times where the locale's explicit year-month-day
 * punctuation reads less like a machine field.
 */
export const formatKoreanDateTime = (
  iso: string | null | undefined,
  fallback = '—'
): string => {
  if (!iso) return fallback
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('ko-KR', { hour12: false })
}
