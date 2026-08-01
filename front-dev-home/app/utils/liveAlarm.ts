// Pure helpers for the live alarm board. Everything here is deterministic
// and clock-free so the board's time-dependent behaviour can be tested
// without faking timers.

export interface LiveAlarmEvent {
  id: string
  eqp_id: string
  alid: string
  kind: 'align' | 'meas'
  alarm_name: string
  occurred_at: string
  occurred_epoch: number
  recipe_id: string
  operation_desc: string
  lot_type_cd: string
}

export type FeedStatus = 'live' | 'stale' | 'not_configured'

export interface LiveAlarmPayload {
  fab_name: string
  tool_type: string
  feed_status: FeedStatus
  // Last SUCCESSFUL office fetch — null when there has never been one. The
  // server stamps it only on success, so it ages during an outage rather
  // than claiming freshness over data that never arrived.
  fetched_at: string | null
  covered_since: string | null
  server_now: string
  board_window_sec: number
  // Alarms in this facility's feed whose equipment is absent from the
  // sem_list roster, so they belong to no fab. Shown as a count, never as
  // rows: they cannot be attributed to the fab being viewed.
  unmatched_count: number
  events: LiveAlarmEvent[]
}

// Which ids arrived since the previous poll. Per-viewer by design: "new"
// means new to the person watching, not new to the fab.
export const diffNewIds = (prev: string[], next: string[]): string[] => {
  const seen = new Set(prev)
  return next.filter(id => !seen.has(id))
}

export const formatElapsed = (ms: number): string => {
  if (ms < 1000) return '방금'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}초 전`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}분 전`
  return `${Math.floor(minutes / 60)}시간 전`
}

export const boardCounts = (events: LiveAlarmEvent[]): { align: number, meas: number } => ({
  align: events.filter(e => e.kind === 'align').length,
  meas: events.filter(e => e.kind === 'meas').length
})
