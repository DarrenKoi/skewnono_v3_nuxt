// The `window_weeks` axis the two lab pages (TTTM, PM 플래닝) gather data over.
//
// Mirrors back_dev_home/ebeam/_analysis_window.py — the server refuses a value
// outside its choices with a 400 rather than clamping it, so the client must
// only ever send one of these. The default is two weeks — user decision
// (2026-08-26): a second week to confirm the first at half the cost of the
// widest choice; "not enough runs" was the complaint that created the axis.

export const WINDOW_WEEKS = [1, 2, 3, 4] as const
export type WindowWeeks = typeof WINDOW_WEEKS[number]
export const DEFAULT_WINDOW_WEEKS: WindowWeeks = 2

export const isWindowWeeks = (value: unknown): value is WindowWeeks =>
  (WINDOW_WEEKS as readonly unknown[]).includes(value)

/**
 * A stored or otherwise untrusted value, reconciled to a choice the server
 * accepts. Anything else — a number outside the choices, a string, an entry
 * written before the field existed — falls back to the default rather than
 * being sent and 400ing the page.
 */
export const normalizeWindowWeeks = (raw: unknown): WindowWeeks =>
  isWindowWeeks(raw) ? raw : DEFAULT_WINDOW_WEEKS

export const windowDays = (weeks: WindowWeeks) => 7 * weeks

/** The meta bar's cadence readout — from the PAYLOAD's echo, not the request. */
export const windowLabel = (weeks: number) => `${weeks}주 윈도우`
