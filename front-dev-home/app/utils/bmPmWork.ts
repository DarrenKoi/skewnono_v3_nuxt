// Pure display helpers for the BM/PM master-detail panel.
//
// Job stamps arrive on the hardware `bm-pm` contract as fixed-width local
// wall-clock strings — `_shared.py`'s TS_FMT ("%Y-%m-%d %H:%M"), which both the
// mock and the office adapter normalize through. That fixed width is what lets
// the end label read date and time by slice rather than by Date, so no timezone
// gets to reinterpret a string the backend already formatted for display.

const toEpoch = (ts: string): number | null => {
  const t = Date.parse(ts.replace(' ', 'T'))
  return Number.isFinite(t) ? t : null
}

/**
 * Elapsed time between a job's Down and Up stamps: '9h 15m', '8h', '45m'.
 * Empty when either stamp is missing, unparseable, or out of order — the
 * caller decides whether that reads as "still down" or "no record".
 */
export const workDuration = (start: string, end: string): string => {
  const from = toEpoch(start)
  const to = toEpoch(end)
  if (from === null || to === null || to < from) return ''
  const minutes = Math.round((to - from) / 60_000)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return `${rest}m`
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

/**
 * The Up stamp shortened against the Down stamp it sits beside: 'HH:MM' when
 * the job ended the same day, 'MM-DD HH:MM' when it ran past midnight. Empty
 * when there is no Up record (the tool is still down).
 */
export const workEndLabel = (start: string, end: string): string => {
  if (!end) return ''
  // Anything not in TS_FMT width is shown as-is rather than sliced into a blank.
  if (end.length < 16) return end
  const time = end.slice(11, 16)
  return end.slice(0, 10) === start.slice(0, 10) ? time : `${end.slice(5, 10)} ${time}`
}
